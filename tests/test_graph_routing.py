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


def test_generate_variants_for_different_questions():
    trust_state = {
        "question": "How can IXOR earn users' trust in agentic AI?",
        "original_question": "How can IXOR earn users' trust in agentic AI?",
        "documents": [
            {
                "page_content": "Trust in agentic AI depends on transparency, predictability, and respectful design. Agents must explain decisions and let users review or pause actions."
            }
        ],
        "retry_count": 0,
        "generation": "",
        "is_relevant": True,
    }
    autonomy_state = {
        "question": "What is IXOR's view on autonomy vs accountability?",
        "original_question": "What is IXOR's view on autonomy vs accountability?",
        "documents": [
            {
                "page_content": "Business Architecture links autonomy and accountability by defining responsibilities, boundaries, and oversight. The system should stay aligned with business goals and ethical standards."
            }
        ],
        "retry_count": 0,
        "generation": "",
        "is_relevant": True,
    }

    trust_result = generate(trust_state)
    autonomy_result = generate(autonomy_state)

    assert trust_result["generation"] != autonomy_result["generation"]
    assert "trust" in trust_result["generation"].lower()
    assert "autonomy" in autonomy_result["generation"].lower()
    assert "accountability" in autonomy_result["generation"].lower()

    from src.graph import run_agent

    trust_answer = run_agent("How can IXOR earn users' trust in agentic AI?")[
        "generation"
    ]
    autonomy_answer = run_agent("What is IXOR's view on autonomy vs accountability?")[
        "generation"
    ]

    assert trust_answer != autonomy_answer
    assert "trust" in trust_answer.lower()
    assert (
        "autonomy" in autonomy_answer.lower()
        or "accountability" in autonomy_answer.lower()
    )


def test_bogus_question_falls_back_instead_of_generating():
    from src.graph import run_agent

    result = run_agent("X")

    assert result["generation"].startswith("I couldn't find sufficient IXOR material")
    assert result["retry_count"] == 2
