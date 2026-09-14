from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "ixor_papers"


class SimpleVectorStore:
    """Minimal local retrieval store for the IXOR corpus.

    This avoids external model dependencies while still giving the app a real
    corpus-backed search layer. It ranks documents by overlap between the query
    tokens and the corpus text, which is enough for the POC and testing flow.
    """

    def __init__(self, data_dir: Path | str = DATA_DIR):
        self.data_dir = Path(data_dir)
        self.documents = self._load_documents()

    def _load_documents(self) -> List[Dict[str, Any]]:
        if not self.data_dir.exists():
            return []

        docs: List[Dict[str, Any]] = []
        for path in sorted(self.data_dir.glob("*.txt")):
            text = path.read_text(encoding="utf-8")
            title = self._extract_title(text)
            docs.append(
                {
                    "source": path.name,
                    "title": title,
                    "page_content": text,
                }
            )
        return docs

    @staticmethod
    def _extract_title(text: str) -> str:
        match = re.search(r"^Title:\s*(.+)$", text, re.MULTILINE)
        return match.group(1).strip() if match else "IXOR document"

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        normalized = text.lower().replace("’", "'").replace("“", '"').replace("”", '"')
        return re.findall(r"[a-z0-9']+", normalized)

    @staticmethod
    def _score(query: str, document_text: str) -> float:
        q_tokens = Counter(SimpleVectorStore._tokenize(query))
        d_tokens = Counter(SimpleVectorStore._tokenize(document_text))
        if not q_tokens:
            return 0.0

        overlap = sum(min(q_tokens[token], d_tokens[token]) for token in q_tokens)
        query_length = sum(q_tokens.values())
        doc_length = sum(d_tokens.values())
        if query_length == 0 or doc_length == 0:
            return 0.0

        return overlap / max(1, min(query_length, doc_length))

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        scored: List[tuple[float, Dict[str, Any]]] = []
        for doc in self.documents:
            score = self._score(query, doc["page_content"])
            scored.append((score, doc))

        ranked = sorted(scored, key=lambda item: item[0], reverse=True)
        results: List[Dict[str, Any]] = []
        for score, doc in ranked[:top_k]:
            if score <= 0:
                continue
            results.append(
                {
                    "page_content": doc["page_content"],
                    "source": doc["source"],
                    "title": doc["title"],
                    "score": score,
                }
            )

        return results


_vector_store = SimpleVectorStore()


def get_vector_store() -> SimpleVectorStore:
    return _vector_store
