from __future__ import annotations

import re
from collections import Counter
from typing import Any

from pydantic import BaseModel, Field

from src.llm import generate_with_llm
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
_DOMAIN_TERMS = {
    "accountability",
    "agent",
    "agentic",
    "autonomy",
    "deterministic",
    "predictability",
    "transparency",
    "trust",
}

# Expands a recognized domain term toward corpus vocabulary it co-occurs with,
# so retries search for related concepts instead of repeating the same query.
_DOMAIN_SYNONYMS: dict[str, list[str]] = {
    "trust": ["transparency", "predictability", "respectful", "reliability"],
    "transparency": ["trust", "explain", "predictability"],
    "predictability": ["consistent", "trust", "reliability"],
    "autonomy": ["accountability", "boundaries", "oversight"],
    "accountability": ["autonomy", "oversight", "responsibility"],
    "agent": ["agentic", "automation", "deterministic"],
    "agentic": ["agent", "autonomous", "automation"],
    "deterministic": ["agent", "automation", "workflow"],
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


def retrieve(state: GraphState) -> GraphState:
    _ensure_telemetry(state)
    vector_store = get_vector_store()
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
    question_tokens = _meaningful_tokens(state["original_question"])
    relevant = False

    for document in state["documents"]:
        document_tokens = _meaningful_tokens(document["page_content"])
        overlap = question_tokens & document_tokens
        retrieval_score = document.get("score", 1.0)

        # Two meaningful shared terms provide a small but useful lexical signal.
        # A single domain term is enough only for a very short, focused question.
        if (len(overlap) >= 2 and retrieval_score >= 0.1) or (
            len(question_tokens) == 1 and overlap.intersection(_DOMAIN_TERMS)
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

    original_tokens = _meaningful_tokens(state["original_question"])
    domain_hits = sorted(original_tokens & _DOMAIN_TERMS)

    if domain_hits:
        # Expand recognized domain terms toward related corpus vocabulary.
        # Later attempts pull in a wider set of synonyms instead of repeating
        # the exact same expansion as the previous retry.
        expansions: list[str] = []
        for term in domain_hits:
            expansions.extend(_DOMAIN_SYNONYMS.get(term, []))
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
        extra = (
            "trust transparency predictability agentic AI"
            if attempt == 1
            else "autonomy accountability deterministic automation"
        )

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

    llm_answer = generate_with_llm(state["original_question"], state["documents"])
    if llm_answer:
        state["generation"] = llm_answer["answer"]
        state["telemetry"]["llm"] = {
            key: value for key, value in llm_answer.items() if key != "answer"
        }
        return state

    combined = "\n\n".join(doc["page_content"] for doc in state["documents"])
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


def fallback(state: GraphState) -> GraphState:
    state["generation"] = (
        "I couldn't find sufficient IXOR material to answer this confidently. "
        "Please rephrase the question or ask about trust, predictability, or agent suitability."
    )
    return state
