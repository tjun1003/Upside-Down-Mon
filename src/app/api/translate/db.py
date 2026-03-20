"""
MongoDB helper (async) for the translation backend.

Provides:
- `init_mongo(app)` / `close_mongo(app)` to manage a Motor client on FastAPI app.state
- `MongoConversationStore` — simple async store for messages
- `MongoKnowledgeBase` — minimal persistence for KB documents

This file is intentionally small and synchronous-friendly for easy integration
with `translation.py`'s startup event handlers.
"""
from typing import List, Dict, Any, Optional
import os

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB = os.getenv("MONGODB_DB", "sea_translate")


async def init_mongo(app: FastAPI) -> None:
    """Initialize Motor client and attach `mongodb` to `app.state`.

    Safe to call when `MONGODB_URI` is empty — in that case no client is created.
    """
    if not MONGODB_URI:
        app.state.mongodb_client = None
        app.state.mongodb = None
        return

    client = AsyncIOMotorClient(MONGODB_URI)
    app.state.mongodb_client = client
    app.state.mongodb = client[MONGODB_DB]

    # Create lightweight indexes (best-effort).
    try:
        await app.state.mongodb.messages.create_index([("session_id", 1), ("ts", 1)])
        await app.state.mongodb.kb_docs.create_index([("metadata.lang", 1)])
        # Text index could be added if desired: await app.state.mongodb.kb_docs.create_index([('text', 'text')])
    except Exception:
        # Index creation is optional — ignore failures here.
        pass


def close_mongo(app: FastAPI) -> None:
    client = getattr(app.state, "mongodb_client", None)
    if client:
        client.close()


class MongoConversationStore:
    """A minimal async conversation store backed by MongoDB.

    Collection: `messages` with documents:
      { session_id, role: 'user'|'ai', text, ts }
    """

    def __init__(self, db: Any):
        self.db = db

    async def add(self, session_id: str, human: str, ai: str, ts: Optional[float] = None) -> None:
        import time
        if ts is None:
            ts = time.time()
        # Insert human then assistant message (keeps ordering by ts)
        await self.db.messages.insert_many([
            {"session_id": session_id, "role": "user", "text": human, "ts": ts},
            {"session_id": session_id, "role": "ai", "text": ai, "ts": ts + 0.0001},
        ])

    async def history(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self.db.messages.find({"session_id": session_id}).sort("ts", 1).limit(limit)
        return await cursor.to_list(length=limit)

    async def clear(self, session_id: str) -> None:
        await self.db.messages.delete_many({"session_id": session_id})

    async def active_sessions(self) -> int:
        sessions = await self.db.messages.distinct("session_id")
        return len(sessions or [])


class MongoKnowledgeBase:
    """Mongo-backed KB data access.

    This class intentionally exposes low-level CRUD-ish operations only.
    RAG orchestration (query strategy and context formatting) should live in rag_service.py.
    """

    def __init__(self, db: Any):
        self.db = db

    async def add_documents(self, docs: List[Dict[str, Any]]) -> int:
        if not docs:
            return 0
        res = await self.db.kb_docs.insert_many(docs)
        return len(res.inserted_ids)

    async def find_documents(
        self,
        query_filter: Optional[Dict[str, Any]] = None,
        projection: Optional[Dict[str, Any]] = None,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        query_filter = query_filter or {}
        projection = projection or {"_id": 0}
        safe_limit = max(1, int(limit))
        cursor = self.db.kb_docs.find(query_filter, projection).limit(safe_limit)
        return await cursor.to_list(length=safe_limit)
