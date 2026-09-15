from __future__ import annotations

import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gemini-2.5-flash"


_CONTEXT_STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "can",
    "does",
    "for",
    "how",
    "in",
    "is",
    "of",
    "on",
    "say",
    "the",
    "to",
    "what",
    "when",
    "we",
    "why",
}


def _context_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9']+", text.lower())
        if token not in _CONTEXT_STOP_WORDS and len(token) > 1
    }


def _context(documents: list[dict[str, Any]], question: str) -> str:
    question_tokens = _context_tokens(question)
    selected_sources: list[str] = []
    total_chars = 0
    max_chars = 8_000

    for document in documents:
        sentences = re.split(r"(?<=[.!?])\s+", document["page_content"])
        ranked_sentences = sorted(
            enumerate(sentences),
            key=lambda item: (
                len(question_tokens & _context_tokens(item[1])),
                -item[0],
            ),
            reverse=True,
        )
        selected = [sentence for _, sentence in ranked_sentences[:2] if sentence]
        source = document.get("source", "IXOR source")
        excerpt = f"[{source}]\n" + " ".join(selected)
        if total_chars + len(excerpt) > max_chars:
            break
        selected_sources.append(excerpt)
        total_chars += len(excerpt)

    return "\n\n".join(selected_sources)


def generate_with_llm(
    question: str, documents: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Generate a grounded answer when the optional external provider is enabled."""
    provider = os.getenv("IXOR_LLM_PROVIDER")
    if provider is None:
        provider = "gemini" if os.getenv("GEMINI_API_KEY") else "local"
    if provider.lower() != "gemini":
        return None

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=15_000),
        )
        context = _context(documents, question)
        response = client.models.generate_content(
            model=os.getenv("IXOR_LLM_MODEL", DEFAULT_MODEL),
            contents=(
                "Answer only from these IXOR excerpts. Use 2-4 complete sentences, "
                "maximum 120 words. Cite source filenames in square brackets and "
                "do not invent facts.\n\n"
                f"Question: {question}\n\n"
                f"IXOR source excerpts:\n{context}"
            ),
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=500,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        finish_reason = response.candidates[0].finish_reason
        if str(finish_reason).endswith("MAX_TOKENS"):
            return None
        answer = response.text
        answer = answer.strip() if answer else ""
        if len(answer.split()) < 12 or not answer[-1] in ".!?]":
            return None
        usage = getattr(response, "usage_metadata", None)
        return {
            "answer": answer,
            "provider": "gemini",
            "model": os.getenv("IXOR_LLM_MODEL", DEFAULT_MODEL),
            "context_chars": len(context),
            "prompt_tokens": getattr(usage, "prompt_token_count", None),
            "output_tokens": getattr(usage, "candidates_token_count", None),
            "total_tokens": getattr(usage, "total_token_count", None),
            "finish_reason": str(finish_reason),
        }
    except Exception:
        # The local deterministic generator remains available when the provider,
        # credentials, or network are unavailable.
        return None
