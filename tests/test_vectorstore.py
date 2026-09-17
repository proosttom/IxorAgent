from src.vectorstore import get_vector_store


def test_get_vector_store_returns_distinct_stores_per_corpus():
    ixor_store = get_vector_store("ixor_papers")
    cv_store = get_vector_store("cv_job_fit")

    assert ixor_store is not cv_store
    assert get_vector_store("ixor_papers") is ixor_store


def test_cv_job_fit_corpus_contains_cv_and_job_posting():
    store = get_vector_store("cv_job_fit")
    sources = {doc["source"] for doc in store.documents}

    assert "cv_tom_proost.txt" in sources
    assert "job_posting.txt" in sources


def test_cv_job_fit_search_finds_relevant_terms():
    store = get_vector_store("cv_job_fit")
    results = store.search("Python experience", top_k=3)

    assert results
    assert any("python" in doc["page_content"].lower() for doc in results)
