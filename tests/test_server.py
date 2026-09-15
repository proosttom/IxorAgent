import pytest
from fastapi.testclient import TestClient

from src.server import app


@pytest.fixture(autouse=True)
def disable_external_llm(monkeypatch):
    monkeypatch.setenv("IXOR_LLM_PROVIDER", "local")


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ixor-agent"}


def test_ask_returns_answer_and_telemetry(client):
    response = client.post(
        "/ask",
        json={"question": "How is trust in AI earned?", "verbose": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert body["telemetry"]["request_id"]
    assert "retrieval_steps" not in body["telemetry"]
    assert body["telemetry"]["relevance"]["is_relevant"] is True


def test_ask_rejects_empty_question(client):
    response = client.post("/ask", json={"question": "   "})

    assert response.status_code in {400, 422}


def test_ask_rejects_question_over_limit(client):
    response = client.post("/ask", json={"question": "x" * 1_001})

    assert response.status_code == 422
