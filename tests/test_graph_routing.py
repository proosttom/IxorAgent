import pytest

from src.nodes import (
    decide_to_generate,
    generate,
    grade_documents,
    retrieve,
    rewrite_query,
)
from src.state import GraphState


@pytest.fixture
def mock_state() -> GraphState:
    return {
        "question": "How can we earn users' trust in agentic AI?",
        "original_question": "How can we earn users' trust in agentic AI?",
        "documents": [],
        "retry_count": 0,
        "generation": "",
        "is_relevant": False,
    }


@pytest.fixture(autouse=True)
def disable_external_llm(monkeypatch):
    monkeypatch.setenv("IXOR_LLM_PROVIDER", "local")


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
    assert all("chunk_id" in doc and "score" in doc for doc in result["documents"])


def test_retrieval_prefers_source_diversity(mock_state):
    mock_state["question"] = "how is trust in AI earned?"
    result = retrieve(mock_state)

    sources = [document["source"] for document in result["documents"]]

    assert len(sources) == len(set(sources))


def test_relevance_requires_retrieval_score(mock_state):
    mock_state["documents"] = [
        {
            "page_content": "Trust in agentic AI depends on transparency.",
            "score": 0.05,
        }
    ]

    result = grade_documents(mock_state)

    assert result["is_relevant"] is False


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


def test_grade_documents_requires_meaningful_overlap(mock_state):
    mock_state["question"] = "What does IXOR say about trust in gardening?"
    mock_state["original_question"] = mock_state["question"]
    mock_state["documents"] = [
        {
            "page_content": "IXOR explains that trust in agentic AI depends on transparency and predictability."
        }
    ]

    result = grade_documents(mock_state)

    assert result["is_relevant"] is False
    assert decide_to_generate(result) == "rewrite_query"


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
    mock_state["is_relevant"] = True
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


def test_generation_remains_local_when_external_llm_is_disabled(
    mock_state, monkeypatch
):
    monkeypatch.setenv("IXOR_LLM_PROVIDER", "local")
    mock_state["documents"] = [
        {
            "page_content": "Trust in agentic AI depends on transparency and predictability."
        }
    ]
    mock_state["is_relevant"] = True

    result = generate(mock_state)

    assert "transparency" in result["generation"].lower()


def test_context_selection_preserves_source_and_limits_size():
    from src.llm import _context

    context = _context(
        [
            {
                "source": "trust.txt",
                "page_content": "Trust depends on transparency. " + ("Noise. " * 2_000),
            }
        ],
        "How does trust depend on transparency?",
    )

    assert "[trust.txt]" in context
    assert "Trust depends on transparency." in context
    assert len(context) <= 8_000


def test_rewrite_query_differs_across_consecutive_retries(mock_state):
    mock_state["question"] = "How is trust earned?"
    mock_state["original_question"] = "How is trust earned?"

    first = rewrite_query(dict(mock_state))
    second = rewrite_query(dict(first))

    assert first["question"] != second["question"]
    assert second["retry_count"] == 2


def test_rewrite_query_expands_recognized_domain_terms(mock_state):
    mock_state["question"] = "How is trust earned?"
    mock_state["original_question"] = "How is trust earned?"

    result = rewrite_query(mock_state)

    assert result["question"] != "How is trust earned? IXOR impact papers"
    assert any(
        term in result["question"].lower()
        for term in ("transparency", "predictability", "reliability", "respectful")
    )


def test_retrieve_widens_top_k_on_retries(mock_state):
    mock_state["question"] = "trust"
    mock_state["retry_count"] = 0
    first_pass = retrieve(dict(mock_state))

    mock_state["retry_count"] = 1
    second_pass = retrieve(dict(mock_state))

    assert len(second_pass["documents"]) >= len(first_pass["documents"])


def test_cv_job_fit_corpus_routes_and_grades_independently(mock_state):
    mock_state["corpus"] = "cv_job_fit"
    mock_state["question"] = "What Python experience does the candidate have?"
    mock_state["original_question"] = mock_state["question"]

    result = retrieve(mock_state)
    assert result["documents"]
    assert any(doc["source"] == "cv_tom_proost.txt" for doc in result["documents"])

    result = grade_documents(result)
    assert result["is_relevant"] is True
    assert decide_to_generate(result) == "generate"


def test_cv_job_fit_uses_generic_extractive_fallback_locally():
    from src.graph import run_agent

    result = run_agent(
        "What Python experience does the candidate have?", corpus="cv_job_fit"
    )

    assert result["generation"]
    assert "python" in result["generation"].lower()


def test_cv_job_fit_bogus_question_falls_back():
    from src.graph import run_agent

    result = run_agent("zzz gardening unrelated", corpus="cv_job_fit")

    assert "CV or job posting" in result["generation"]


def test_cv_job_fit_matches_plural_domain_terms(mock_state):
    mock_state["corpus"] = "cv_job_fit"
    mock_state["question"] = "What are the biggest caveats?"
    mock_state["original_question"] = mock_state["question"]

    result = retrieve(mock_state)
    result = grade_documents(result)

    assert result["is_relevant"] is True
