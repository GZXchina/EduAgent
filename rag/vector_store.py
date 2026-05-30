from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb

from backend.settings import get_settings
from rag.embeddings import get_embedding_function

logger = logging.getLogger(__name__)


@lru_cache
def get_chroma_client() -> chromadb.PersistentClient:
    settings = get_settings()
    persist = Path(settings.chroma_persist_dir)
    persist.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(persist))


def get_collection():
    settings = get_settings()
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.chroma_collection,
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(chunks: list[dict], *, file_id: str) -> int:
    if not chunks:
        return 0
    col = get_collection()
    ids = [f"{file_id}::{c['metadata']['chunk_index']}" for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [{**c["metadata"], "file_id": file_id} for c in chunks]
    col.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(chunks)


def query_collection(text: str, k: int | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    top_k = k or settings.rag_top_k
    col = get_collection()
    if col.count() == 0:
        return []
    result = col.query(query_texts=[text], n_results=min(top_k, col.count()))
    out: list[dict[str, Any]] = []
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]
    for doc, meta, dist in zip(docs, metas, dists, strict=False):
        score = 1.0 - float(dist) if dist is not None else 0.0
        out.append({"text": doc, "score": round(score, 4), "meta": meta or {}})
    return out


def collection_stats() -> dict[str, Any]:
    col = get_collection()
    return {"count": col.count(), "name": col.name}
