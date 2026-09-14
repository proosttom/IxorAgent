import pytest

from src.nodes import decide_to_generate, generate, grade_documents, retrieve
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


def test_retrieve_uses_ixor_corpus(mock_state):
    mock_state["question"] = "How can IXOR earn users' trust in agentic AI?"
    result = retrieve(mock_state)
    assert result["documents"]

    normalized_docs = [
        doc["page_content"].lower().replace("’", "'") for doc in result["documents"]
    ]

    assert any("trust" in doc and "agentic ai" in doc for doc in normalized_docs)
    assert any("users" in doc and "trust" in doc for doc in normalized_docs)


def test_relevant_docs_route_to_generate(mock_state):
    mock_state["documents"] = [
        {
            "page_content": "IXOR explains how to earn users' trust in agentic AI with transparency and predictability."
        }
    ]
    mock_state["question"] = "How can IXOR earn users' trust in agentic AI?"
    result = grade_documents(mock_state)

    assert result["is_relevant"] is True
    assert decide_to_generate(result) == "generate"


def test_generate_returns_polished_summary(mock_state):
    mock_state["documents"] = [
        {
            "page_content": "How to earn users' trust in autonomous systems: trust comes from transparency, predictability, and respectful design. Agents must show confidence levels and let users pause or review actions."
        },
        {
            "page_content": "Not every process needs an agent. Deterministic workflows often work better when clarity and control matter more than autonomy."
        },
    ]
    mock_state["question"] = "How can IXOR earn users' trust in agentic AI?"
    result = generate(mock_state)

    assert "trust" in result["generation"].lower()
    assert "transparency" in result["generation"].lower()
    assert "predictability" in result["generation"].lower()
    assert "Title:" not in result["generation"]
    assert "--- PAGE" not in result["generation"]
