from __future__ import annotations

from src.nodes import (
    decide_to_generate,
    fallback,
    generate,
    grade_documents,
    retrieve,
    rewrite_query,
)
from src.state import GraphState


def run_agent(question: str) -> GraphState:
    state: GraphState = {
        "question": question,
        "original_question": question,
        "documents": [],
        "retry_count": 0,
        "generation": "",
    }

    state = retrieve(state)
    state = grade_documents(state)

    while True:
        route = decide_to_generate(state)
        if route == "generate":
            state = generate(state)
            break
        if route == "rewrite_query":
            if state["retry_count"] >= 2:
                state = fallback(state)
                break
            state = rewrite_query(state)
            state = retrieve(state)
            state = grade_documents(state)
            continue
        if route == "fallback":
            state = fallback(state)
            break

    return state
