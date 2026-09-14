from typing import TypedDict, List, Dict, Any


class GraphState(TypedDict):
    question: str
    original_question: str
    documents: List[Dict[str, Any]]
    retry_count: int
    generation: str
    is_relevant: bool
