from __future__ import annotations

import logging
from functools import lru_cache

from backend.settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_embedding_function():
    """懒加载 SentenceTransformer 嵌入（BGE 系列）。"""
    settings = get_settings()
    model_name = settings.embedding_model
    logger.info("加载 Embedding 模型: %s", model_name)

    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    return SentenceTransformerEmbeddingFunction(model_name=model_name)
