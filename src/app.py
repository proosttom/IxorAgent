from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.graph import run_agent


def print_response(response: dict) -> None:
    print(response["generation"])
    telemetry = response["telemetry"]
    llm = telemetry.get("llm", {})
    print("\nExecution details:")
    print(f"- Retrieval attempts: {len(telemetry.get('retrieval_steps', []))}")
    print(
        f"- Retrieved chunks: {sum(len(step['hits']) for step in telemetry.get('retrieval_steps', []))}"
    )
    for index, step in enumerate(telemetry.get("retrieval_steps", []), start=1):
        print(f"- Retrieval {index} query: {step['query']}")
        for hit in step["hits"]:
            print(
                "  - "
                f"{hit.get('source')} chunk={hit.get('chunk_id')} "
                f"score={hit.get('score', 0):.3f}"
            )
    print(
        f"- Relevance accepted: {telemetry.get('relevance', {}).get('is_relevant', False)}"
    )
    print(f"- Provider: {llm.get('provider', 'local')}")
    if llm.get("model"):
        print(f"- Model: {llm['model']}")
    if llm.get("context_chars") is not None:
        print(f"- LLM context: {llm['context_chars']} characters")
    if llm.get("total_tokens") is not None:
        print(
            "- Tokens: "
            f"{llm.get('prompt_tokens', '?')} prompt + "
            f"{llm.get('output_tokens', '?')} output = "
            f"{llm['total_tokens']} total"
        )


def main() -> None:
    if len(sys.argv) > 1:
        questions = [" ".join(sys.argv[1:])]
    else:
        questions = ["How can IXOR earn users' trust in agentic AI?"]

    if len(sys.argv) == 1:
        print("Ask a question about IXOR and agentic AI. Type 'exit' to quit.")
        while True:
            raw = input("Question: ").strip()
            if raw.lower() in {"exit", "quit", "q"}:
                print("Goodbye.")
                break
            if not raw:
                print("Please enter a question.")
                continue
            response = run_agent(raw)
            print_response(response)
        return

    for question in questions:
        response = run_agent(question)
        print_response(response)


if __name__ == "__main__":
    main()
