from __future__ import annotations

from app.providers.mock_data import MOCK_DOCUMENTS
from app.storage.chroma_store import ChromaStore


def main() -> None:
    store = ChromaStore()
    store.upsert_documents(MOCK_DOCUMENTS)


if __name__ == "__main__":
    main()
