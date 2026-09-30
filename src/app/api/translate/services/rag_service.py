"""RAG Service - Simplified version, only core MongoDB retrieval functionality"""
from typing import Any, Dict, List, Optional


class RAGService:
    """MongoDB RAG retrieval and document management service"""

    def __init__(self, default_kb: Any, logger: Any, top_k: int = 3, text_field: str = "text"):
        self._default_kb = default_kb
        self._logger = logger
        self._top_k = top_k
        self._text_field = text_field
        self._mongo_kb_store: Optional[Any] = None

    def set_mongo_store(self, mongo_kb_store: Optional[Any]) -> None:
        """Set MongoDB knowledge base storage"""
        self._mongo_kb_store = mongo_kb_store

    async def retrieve_context(self, message: str) -> str:
        """Retrieve relevant context from knowledge base"""
        if not self._default_kb.ready:
            return ""

        try:
            context = self._default_kb.retrieve(message)
            if context.strip():
                self._logger.info(f"RAG: Retrieved context ({len(context)} chars)")
                return context
        except Exception as exc:
            self._logger.error(f"RAG retrieval failed: {exc}")

        return ""

    async def add_documents(self, documents: List[Dict[str, Any]]) -> int:
        """Add documents to knowledge base"""
        mongo_added = 0
        
        # Write to MongoDB first
        if self._mongo_kb_store:
            try:
                mongo_added = await self._mongo_kb_store.add_documents(documents)
            except Exception as exc:
                self._logger.error(f"MongoDB write failed: {exc}")

        # Sync to in-memory KB
        try:
            self._default_kb.add_documents(documents)
        except Exception as exc:
            self._logger.error(f"In-memory KB write failed: {exc}")

        return mongo_added
