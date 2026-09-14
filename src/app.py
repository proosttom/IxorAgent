from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.graph import run_agent

if __name__ == "__main__":
    question = "How can IXOR earn users' trust in agentic AI?"
    response = run_agent(question)
    print(response["generation"])
