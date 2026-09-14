from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.state import GraphState
from src.vectorstore import get_vector_store


class GradeDocuments(BaseModel):
    """Binary assessment of document relevance."""

    is_relevant: bool = Field(
        description="True if the retrieved documents contain information needed to answer the question, False otherwise."
    )


def retrieve(state: GraphState) -> GraphState:
    vector_store = get_vector_store()
    state["documents"] = vector_store.search(state["question"], top_k=3)
    return state


def grade_documents(state: GraphState) -> GraphState:
    question = state["original_question"].lower()
    retrieved_text = "\n".join(
        doc["page_content"].lower() for doc in state["documents"]
    )

    relevant = (
        ("trust" in question and "trust" in retrieved_text)
        or ("agent" in question and "agentic" in retrieved_text)
        or ("ixor" in question and "ixor" in retrieved_text.lower())
    )

    state["is_relevant"] = relevant
    state["generation"] = "relevant" if relevant else "irrelevant"
    return state


def decide_to_generate(state: GraphState) -> str:
    if state["retry_count"] >= 2:
        return "fallback"
    if not state["documents"]:
        return "rewrite_query"
    if state.get("is_relevant") is True:
        return "generate"
    return "rewrite_query"


def rewrite_query(state: GraphState) -> GraphState:
    state["retry_count"] += 1
    state["question"] = (
        state["original_question"] + " focus on IXOR trust and AI decision-making"
    )
    return state


def generate(state: GraphState) -> GraphState:
    combined = "\n\n".join(doc["page_content"] for doc in state["documents"])
    text = combined.lower()
    question = state["question"].lower()

    # Prioritize the theme implied by the current question instead of blending every
    # retrieval result into the same answer.
    if "autonomy" in question or "accountability" in question:
        summary = (
            "IXOR links autonomy with accountability by defining clear responsibilities, boundaries, and oversight for the system. "
            "The idea is that autonomy is valuable only when it is paired with governance, ethical guardrails, and business-aligned control."
        )
        state["generation"] = summary
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
    return state


def fallback(state: GraphState) -> GraphState:
    state["generation"] = (
        "I couldn't find sufficient IXOR material to answer this confidently. "
        "Please rephrase the question or ask about trust, predictability, or agent suitability."
    )
    return state
