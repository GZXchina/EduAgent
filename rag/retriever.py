from __future__ import annotations

import logging
from typing import Any

from backend.settings import get_settings
from rag.vector_store import query_collection

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    """RAG 检索：ChromaDB + BGE 嵌入。"""

    def __init__(self, persist_dir: str | None = None) -> None:
        self.persist_dir = persist_dir or get_settings().chroma_persist_dir

    async def query(self, text: str, k: int | None = None) -> list[dict[str, Any]]:
        try:
            return query_collection(text, k=k)
        except Exception as exc:
            logger.warning("RAG 检索失败: %s", exc)
            return []
