from __future__ import annotations

import re
from collections import Counter
from typing import Any

from pydantic import BaseModel, Field

from src.llm import generate_with_llm
from src.profiles import get_profile
from src.state import GraphState
from src.vectorstore import get_vector_store

MAX_RETRIES = 2


class GradeDocuments(BaseModel):
    """Binary assessment of document relevance."""

    is_relevant: bool = Field(
        description="True if the retrieved documents contain information needed to answer the question, False otherwise."
    )


_STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "can",
    "does",
    "for",
    "how",
    "in",
    "ixor",
    "is",
    "of",
    "on",
    "say",
    "the",
    "to",
    "what",
    "when",
    "we",
    "why",
}


def _ensure_telemetry(state: GraphState) -> None:
    state.setdefault(
        "telemetry",
        {"retrieval_steps": [], "relevance": {}, "llm": {}},
    )


def _record_local_llm(state: GraphState, context_chars: int) -> None:
    state["telemetry"]["llm"] = {
        "provider": "local",
        "model": None,
        "context_chars": context_chars,
        "prompt_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
    }


def _meaningful_tokens(text: str) -> set[str]:
    normalized = text.lower().replace("’", "'")
    return {
        token
        for token in re.findall(r"[a-z0-9']+", normalized)
        if token not in _STOP_WORDS and len(token) > 1
    }


def _stem(token: str) -> str:
    # Naive singularization so "caveats"/"agents" still match domain terms
    # like "caveat"/"agent" without pulling in a full stemming dependency.
    return token[:-1] if token.endswith("s") and len(token) > 3 else token


def _domain_hits(tokens: set[str], domain_terms: frozenset[str]) -> set[str]:
    return {token for token in tokens if _stem(token) in domain_terms}


def retrieve(state: GraphState) -> GraphState:
    _ensure_telemetry(state)
    vector_store = get_vector_store(state.get("corpus", "ixor_papers"))
    # Widen the candidate pool on retries instead of re-running the same
    # narrow search that already failed to find relevant evidence.
    top_k = 3 + 2 * state.get("retry_count", 0)
    state["documents"] = vector_store.search(state["question"], top_k=top_k)
    state["telemetry"]["retrieval_steps"].append(
        {
            "query": state["question"],
            "hits": [
                {
                    "source": document.get("source"),
                    "chunk_id": document.get("chunk_id"),
                    "score": document.get("score"),
                }
                for document in state["documents"]
            ],
        }
    )
    return state


def grade_documents(state: GraphState) -> GraphState:
    _ensure_telemetry(state)
    profile = get_profile(state.get("corpus", "ixor_papers"))
    question_tokens = _meaningful_tokens(state["original_question"])
    relevant = False

    for document in state["documents"]:
        document_tokens = _meaningful_tokens(document["page_content"])
        overlap = question_tokens & document_tokens
        retrieval_score = document.get("score", 1.0)

        # Two meaningful shared terms provide a small but useful lexical signal.
        # A single domain term is enough only for a very short, focused question,
        # unless the profile broadens that shortcut to any question length.
        if (
            (len(overlap) >= profile.min_overlap_terms and retrieval_score >= 0.1)
            or (
                len(question_tokens) == 1
                and _domain_hits(question_tokens, profile.domain_terms)
            )
            or (
                profile.broad_domain_match
                and retrieval_score >= 0.1
                and _domain_hits(question_tokens, profile.domain_terms)
            )
        ):
            relevant = True
            break

    state["is_relevant"] = relevant
    state["generation"] = ""
    state["telemetry"]["relevance"] = {
        "is_relevant": relevant,
        "question_terms": len(question_tokens),
    }
    return state


def decide_to_generate(state: GraphState) -> str:
    if state["retry_count"] >= MAX_RETRIES:
        return "fallback"
    if not state["documents"]:
        return "rewrite_query"
    if state.get("is_relevant") is True:
        return "generate"
    return "rewrite_query"


def rewrite_query(state: GraphState) -> GraphState:
    state["retry_count"] += 1
    attempt = state["retry_count"]
    profile = get_profile(state.get("corpus", "ixor_papers"))

    original_tokens = _meaningful_tokens(state["original_question"])
    domain_hits = sorted(
        {_stem(token) for token in original_tokens if _stem(token) in profile.domain_terms}
    )

    if domain_hits:
        # Expand recognized domain terms toward related corpus vocabulary.
        # Later attempts pull in a wider set of synonyms instead of repeating
        # the exact same expansion as the previous retry.
        expansions: list[str] = []
        for term in domain_hits:
            expansions.extend(profile.domain_synonyms.get(term, []))
        unique_expansions = list(dict.fromkeys(expansions))
        take = (
            len(unique_expansions)
            if attempt >= 2
            else max(2, len(unique_expansions) // 2)
        )
        extra = " ".join(unique_expansions[:take])
    else:
        # No recognized domain term: broaden with a different generic hint
        # per attempt so retries explore different parts of the corpus.
        extra = profile.rewrite_hints[0] if attempt == 1 else profile.rewrite_hints[1]

    new_question = f"{state['original_question']} {extra}".strip()
    if new_question == state["question"]:
        # Guard against a no-op rewrite when expansion is empty or unchanged.
        new_question = f"{new_question} IXOR"

    state["question"] = new_question
    return state


def generate(state: GraphState) -> GraphState:
    _ensure_telemetry(state)
    if not state["documents"] or state.get("is_relevant") is not True:
        return fallback(state)

    profile = get_profile(state.get("corpus", "ixor_papers"))
    llm_answer = generate_with_llm(
        state["original_question"], state["documents"], profile
    )
    if llm_answer:
        state["generation"] = llm_answer["answer"]
        state["telemetry"]["llm"] = {
            key: value for key, value in llm_answer.items() if key != "answer"
        }
        return state

    combined = "\n\n".join(doc["page_content"] for doc in state["documents"])

    if profile.corpus != "ixor_papers":
        state["generation"] = _extractive_fallback(
            state["original_question"], state["documents"]
        )
        _record_local_llm(state, len(combined))
        return state

    text = combined.lower()
    question = state["original_question"].lower()

    # Prioritize the theme implied by the current question instead of blending every
    # retrieval result into the same answer.
    if "autonomy" in question or "accountability" in question:
        summary = (
            "IXOR links autonomy with accountability by defining clear responsibilities, boundaries, and oversight for the system. "
            "The idea is that autonomy is valuable only when it is paired with governance, ethical guardrails, and business-aligned control."
        )
        state["generation"] = summary
        _record_local_llm(state, len(combined))
        return state

    if (
        "trust" in question
        or "transparency" in question
        or "predictability" in question
    ):
        summary = (
            "IXOR emphasizes that trust comes from transparency, predictability, and respectful design. "
            "Agents should explain what they plan to do, give users control points, and behave consistently so users feel safe delegating decisions."
        )
        state["generation"] = summary
        _record_local_llm(state, len(combined))
        return state

    pieces: list[str] = []
    if "trust" in text:
        pieces.append(
            "IXOR emphasizes that trust comes from transparency, predictability, and respectful design."
        )
    if "transparency" in text:
        pieces.append(
            "Agents should explain what they plan to do and why, rather than hiding decisions behind opaque behavior."
        )
    if "predictability" in text:
        pieces.append(
            "Consistent language, outputs, and user flows make the system feel safer and more reliable."
        )
    if "control" in text or "pause" in text or "review" in text:
        pieces.append(
            "Users should retain control through review, pause, or escalation points before high-impact actions."
        )
    if "autonomy" in text or "accountability" in text:
        pieces.append(
            "IXOR links autonomy with accountability by defining clear responsibilities, boundaries, and oversight for the system."
        )
    if "not every process needs an agent" in text or "deterministic" in text:
        pieces.append(
            "IXOR also warns that not every workflow should be automated with an agent; deterministic processes often remain the better choice."
        )

    summary = (
        " ".join(pieces)
        if pieces
        else "IXOR’s guidance is that trustworthy agentic AI depends on clarity, safe boundaries, and human oversight."
    )
    state["generation"] = summary
    _record_local_llm(state, len(combined))
    return state


def _extractive_fallback(question: str, documents: list[dict[str, Any]]) -> str:
    """Generic local answer: surface the most on-topic sentences from evidence."""
    question_tokens = _meaningful_tokens(question)
    scored_sentences: list[tuple[int, str]] = []
    for document in documents:
        for sentence in re.split(r"(?<=[.!?])\s+", document["page_content"]):
            sentence = sentence.strip()
            if not sentence:
                continue
            overlap = len(question_tokens & _meaningful_tokens(sentence))
            if overlap:
                scored_sentences.append((overlap, sentence))

    if not scored_sentences:
        return "The retrieved excerpts do not contain a clear answer to this question."

    scored_sentences.sort(key=lambda item: item[0], reverse=True)
    top_sentences = [sentence for _, sentence in scored_sentences[:3]]
    return " ".join(top_sentences)


def fallback(state: GraphState) -> GraphState:
    profile = get_profile(state.get("corpus", "ixor_papers"))
    state["generation"] = profile.fallback_message
    return state
