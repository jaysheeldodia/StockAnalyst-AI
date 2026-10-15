from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import get_config

try:
    import chromadb
except ImportError:  # pragma: no cover
    chromadb = None


class _FallbackCollection:
    def __init__(self, persist_file: Path) -> None:
        self.persist_file = persist_file
        self.persist_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.persist_file.exists():
            self.persist_file.write_text("[]", encoding="utf-8")

    def _load(self) -> list[dict[str, Any]]:
        return json.loads(self.persist_file.read_text(encoding="utf-8"))

    def _save(self, payload: list[dict[str, Any]]) -> None:
        self.persist_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]) -> None:
        current = {item["id"]: item for item in self._load()}
        for doc_id, document, metadata in zip(ids, documents, metadatas, strict=False):
            current[doc_id] = {"id": doc_id, "document": document, "metadata": metadata}
        self._save(list(current.values()))

    def query(self, query_texts: list[str], n_results: int) -> dict[str, list[list[Any]]]:
        query_terms = {term.lower() for query in query_texts for term in query.split()}
        scored = []
        for item in self._load():
            text = item["document"]
            overlap = sum(1 for term in query_terms if term in text.lower())
            scored.append((max(1.0 - overlap * 0.1, 0.0), item))
        scored.sort(key=lambda item: item[0])
        top = scored[:n_results]
        return {
            "ids": [[item["id"] for _, item in top]],
            "documents": [[item["document"] for _, item in top]],
            "metadatas": [[item["metadata"] for _, item in top]],
            "distances": [[score for score, _ in top]],
        }


class ChromaStore:
    def __init__(self, persist_dir: Path | None = None) -> None:
        config = get_config()
        self.persist_dir = persist_dir or config.chroma_dir
        if chromadb is not None:
            self.client = chromadb.PersistentClient(path=str(self.persist_dir))
            self.collection = self.client.get_or_create_collection(config.retrieval.collection_name)
        else:
            self.client = None
            self.collection = _FallbackCollection(self.persist_dir / f"{config.retrieval.collection_name}.json")

    def upsert_documents(self, documents: list[dict[str, Any]]) -> None:
        if not documents:
            return
        ids = [doc.get("id", str(uuid4())) for doc in documents]
        texts = [doc["text"] for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]
        self.collection.upsert(ids=ids, documents=texts, metadatas=metadatas)

    def query(self, query_texts: list[str], top_k: int) -> list[dict[str, Any]]:
        result = self.collection.query(query_texts=query_texts, n_results=top_k)
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        ids = (result.get("ids") or [[]])[0] or [None] * len(documents)
        return [
            {"id": doc_id, "text": doc, "metadata": meta or {}, "distance": distance}
            for doc_id, doc, meta, distance in zip(
                ids, documents, metadatas, distances, strict=False
            )
        ]
