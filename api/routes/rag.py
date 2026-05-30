from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from rag.ingest import get_ingest_summary, ingest_knowledge_directory
from rag.retriever import KnowledgeRetriever

router = APIRouter(prefix="/api/rag", tags=["rag"])


class RagQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=4, ge=1, le=20)


class RagQueryResponse(BaseModel):
    query: str
    results: list[dict[str, Any]]


@router.get("/stats")
async def rag_stats() -> dict:
    return get_ingest_summary()


@router.post("/ingest")
async def rag_ingest(background_tasks: BackgroundTasks, sync: bool = False) -> dict:
    if sync:
        n = ingest_knowledge_directory()
        return {"status": "done", "chunks_ingested": n, **get_ingest_summary()}
    background_tasks.add_task(ingest_knowledge_directory)
    return {"status": "started", "message": "后台入库任务已启动，请稍后调用 /api/rag/stats 查看"}


@router.post("/query", response_model=RagQueryResponse)
async def rag_query(body: RagQueryRequest) -> RagQueryResponse:
    retriever = KnowledgeRetriever()
    results = await retriever.query(body.query, k=body.top_k)
    return RagQueryResponse(query=body.query, results=results)
