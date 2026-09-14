from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.graph import run_agent


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
            print(response["generation"])
        return

    for question in questions:
        response = run_agent(question)
        print(response["generation"])


if __name__ == "__main__":
    main()
