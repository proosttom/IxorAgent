from __future__ import annotations

from collections import Counter
import heapq
from pathlib import Path
import re
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "ixor_papers"
CHUNK_SIZE = 2_400
CHUNK_OVERLAP = 300

CORPUS_DIRS: Dict[str, Path] = {
    "ixor_papers": DATA_DIR,
    "cv_job_fit": PROJECT_ROOT / "data" / "cv_job_fit",
}


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
            for index, chunk in enumerate(self._chunk_text(text)):
                docs.append(
                    {
                        "source": path.name,
                        "title": title,
                        "chunk_id": index,
                        "page_content": chunk,
                        "token_counts": Counter(self._tokenize(chunk)),
                    }
                )
        return docs

    @staticmethod
    def _chunk_text(text: str) -> List[str]:
        if len(text) <= CHUNK_SIZE:
            return [text]

        chunks: List[str] = []
        start = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start = end - CHUNK_OVERLAP
        return chunks

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
        return SimpleVectorStore._score_counts(q_tokens, d_tokens)

    @staticmethod
    def _score_counts(
        query_tokens: Counter[str], document_tokens: Counter[str]
    ) -> float:
        q_tokens = query_tokens
        d_tokens = document_tokens
        if not q_tokens:
            return 0.0

        overlap = sum(min(q_tokens[token], d_tokens[token]) for token in q_tokens)
        query_length = sum(q_tokens.values())
        doc_length = sum(d_tokens.values())
        if query_length == 0 or doc_length == 0:
            return 0.0

        return overlap / max(1, min(query_length, doc_length))

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        if top_k <= 0:
            return []

        query_tokens = Counter(self._tokenize(query))
        scored: List[tuple[float, Dict[str, Any]]] = []
        for doc in self.documents:
            score = self._score_counts(query_tokens, doc["token_counts"])
            scored.append((score, doc))

        ranked = heapq.nlargest(len(scored), scored, key=lambda item: item[0])
        selected: List[tuple[float, Dict[str, Any]]] = []
        selected_sources: set[str] = set()

        # Prefer coverage across papers before returning adjacent chunks from the
        # same paper. Remaining slots are filled by the strongest chunks.
        for score, doc in ranked:
            if score <= 0 or doc["source"] in selected_sources:
                continue
            selected.append((score, doc))
            selected_sources.add(doc["source"])
            if len(selected) == top_k:
                break

        if len(selected) < top_k:
            for score, doc in ranked:
                if score <= 0 or (score, doc) in selected:
                    continue
                selected.append((score, doc))
                if len(selected) == top_k:
                    break

        results: List[Dict[str, Any]] = []
        for score, doc in selected:
            results.append(
                {
                    "page_content": doc["page_content"],
                    "source": doc["source"],
                    "title": doc["title"],
                    "chunk_id": doc["chunk_id"],
                    "score": score,
                }
            )

        return results


_stores: Dict[str, SimpleVectorStore] = {}


def get_vector_store(corpus: str = "ixor_papers") -> SimpleVectorStore:
    if corpus not in _stores:
        data_dir = CORPUS_DIRS.get(corpus, DATA_DIR)
        _stores[corpus] = SimpleVectorStore(data_dir)
    return _stores[corpus]
