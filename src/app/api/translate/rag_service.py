from __future__ import annotations

from typing import Any, Dict, List, Optional


class RAGService:
    """Coordinates RAG retrieval/writes across Mongo and fallback KB."""

    def __init__(self, default_kb: Any, logger: Any, top_k: int = 3, text_field: str = "text"):
        self._default_kb = default_kb
        self._logger = logger
        self._top_k = top_k
        self._text_field = text_field
        self._mongo_kb_store: Optional[Any] = None

    def set_mongo_store(self, mongo_kb_store: Optional[Any]) -> None:
        self._mongo_kb_store = mongo_kb_store

    def _format_context(self, docs: List[Dict[str, Any]]) -> str:
        chunks: List[str] = []
        for doc in docs:
            text = str(doc.get(self._text_field, "")).strip()
            if text:
                chunks.append(text)
        return "\n---\n".join(chunks)

    async def retrieve_context(self, message: str) -> str:
        context = ""
        if self._mongo_kb_store is not None:
            try:
                docs = await self._mongo_kb_store.find_documents(
                    query_filter={},
                    projection={"_id": 0, self._text_field: 1},
                    limit=self._top_k,
                )
                context = self._format_context(docs)
            except Exception as exc:
                self._logger.warning(
                    f"Mongo KB retrieval failed, using default KB fallback: {exc}"
                )
                context = ""

        if not context and self._default_kb.ready:
            context = self._default_kb.retrieve(message)

        return context

    async def add_documents(self, documents: List[Dict[str, Any]]) -> int:
        mongo_added = 0
        if self._mongo_kb_store is not None:
            try:
                mongo_added = await self._mongo_kb_store.add_documents(documents)
            except Exception as exc:
                self._logger.warning(f"Mongo KB write failed, using default KB only: {exc}")

        self._default_kb.add_documents(documents)
        return mongo_added
