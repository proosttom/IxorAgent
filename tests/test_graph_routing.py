import pytest

from src.nodes import decide_to_generate
from src.state import GraphState


@pytest.fixture
def mock_state() -> GraphState:
    return {
        "question": "How can we earn users' trust in agentic AI?",
        "original_question": "How can we earn users' trust in agentic AI?",
        "documents": [],
        "retry_count": 0,
        "generation": "",
    }


def test_routing_to_rewrite_when_irrelevant(mock_state):
    mock_state["documents"] = [{"page_content": "Unrelated text about gardening."}]
    assert decide_to_generate(mock_state) == "rewrite_query"


def test_circuit_breaker_on_max_retries(mock_state):
    mock_state["retry_count"] = 2
    mock_state["documents"] = []
    assert decide_to_generate(mock_state) == "fallback"
