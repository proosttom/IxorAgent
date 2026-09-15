from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.graph import run_agent

MAX_QUESTION_LENGTH = 1_000


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ixor-agent"}


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    request_id = str(uuid4())
    try:
        state = run_agent(question)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="The agent could not process this request.",
        ) from None

    telemetry = dict(state["telemetry"])
    telemetry["request_id"] = request_id
    if not request.verbose:
        telemetry = {
            "request_id": request_id,
            "relevance": telemetry.get("relevance", {}),
            "llm": telemetry.get("llm", {}),
        }

    return AskResponse(answer=state["generation"], telemetry=telemetry)
