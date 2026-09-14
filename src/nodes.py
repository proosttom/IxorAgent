from __future__ import annotations

from typing import Any

from src.state import GraphState


def retrieve(state: GraphState) -> GraphState:
    state["documents"] = [
        {
            "page_content": "IXOR focuses on trust in agentic AI through predictability, transparency, and human agency."
        },
        {
            "page_content": "Not every process needs an agent; deterministic workflows often outperform flexible agents."
        },
    ]
    return state


def grade_documents(state: GraphState) -> GraphState:
    question = state["question"].lower()
    relevant = (
        any(
            "trust" in doc["page_content"].lower()
            or "agent" in doc["page_content"].lower()
            for doc in state["documents"]
        )
        and "trust" in question
        or "agent" in question
    )
    state["generation"] = "relevant" if relevant else "irrelevant"
    return state


def decide_to_generate(state: GraphState) -> str:
    if state["retry_count"] >= 2:
        return "fallback"
    if not state["documents"]:
        return "rewrite_query"
    if state["generation"] == "relevant":
        return "generate"
    return "rewrite_query"


def rewrite_query(state: GraphState) -> GraphState:
    state["retry_count"] += 1
    state["question"] = (
        state["original_question"] + " focus on IXOR trust and AI decision-making"
    )
    return state


def generate(state: GraphState) -> GraphState:
    docs = "\n\n".join(doc["page_content"] for doc in state["documents"])
    state["generation"] = f"Based on the IXOR material:\n\n{docs}"
    return state


def fallback(state: GraphState) -> GraphState:
    state["generation"] = (
        "I couldn't find sufficient IXOR material to answer this confidently. "
        "Please rephrase the question or ask about trust, predictability, or agent suitability."
    )
    return state
