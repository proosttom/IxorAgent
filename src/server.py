from __future__ import annotations

import logging
import os
import time
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.graph import run_agent

MAX_QUESTION_LENGTH = 1_000

logging.basicConfig(level=os.getenv("IXOR_LOG_LEVEL", "INFO"))
logger = logging.getLogger("ixor_agent")
# On by default for demo visibility; set IXOR_LOG_QUESTIONS=false to redact
# question text if it may contain personal or confidential information.
LOG_QUESTIONS = os.getenv("IXOR_LOG_QUESTIONS", "true").lower() == "true"


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)
    corpus: Literal["ixor_papers", "cv_job_fit"] = "ixor_papers"
    verbose: bool = True


class AskResponse(BaseModel):
    answer: str
    telemetry: dict[str, Any]


app = FastAPI(
    title="IxorAgent API",
    description="Grounded Q&A over IXOR impact papers.",
    version="1.0.0",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("IXOR_ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/")
def root() -> dict[str, str]:
    # Avoids 404 noise in logs from platform pings and browser visits to "/".
    return {"service": "ixor-agent", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ixor-agent"}


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    request_id = str(uuid4())
    started_at = time.perf_counter()
    try:
        state = run_agent(question, corpus=request.corpus)
    except Exception:
        logger.exception(
            "ask failed request_id=%s corpus=%s", request_id, request.corpus
        )
        raise HTTPException(
            status_code=500,
            detail="The agent could not process this request.",
        ) from None

    telemetry = dict(state["telemetry"])
    telemetry["request_id"] = request_id

    latency_ms = round((time.perf_counter() - started_at) * 1000, 1)
    logger.info(
        "ask request_id=%s corpus=%s latency_ms=%s relevant=%s question=%s",
        request_id,
        request.corpus,
        latency_ms,
        telemetry.get("relevance", {}).get("is_relevant"),
        question if LOG_QUESTIONS else "<redacted>",
    )

    if not request.verbose:
        telemetry = {
            "request_id": request_id,
            "relevance": telemetry.get("relevance", {}),
            "llm": telemetry.get("llm", {}),
        }

    return AskResponse(answer=state["generation"], telemetry=telemetry)
