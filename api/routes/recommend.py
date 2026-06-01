from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.deps import get_db
from services.recommendation_service import RecommendationService

router = APIRouter(prefix="/api/recommend", tags=["recommend"])


class RecommendationItem(BaseModel):
    id: int
    resource_type: str
    resource_label: str
    topic: str
    preview: str
    relevance_score: int
    reasons: list[str]
    content: dict[str, Any]


class RecommendationResponse(BaseModel):
    session_id: str
    profile_found: bool
    profile_summary: str | None = None
    total_resources: int = 0
    message: str | None = None
    recommendations: list[RecommendationItem]


@router.get("/{session_id}", response_model=RecommendationResponse)
async def get_recommendations(
    session_id: str,
    limit: int = Query(default=6, ge=1, le=20),
    db: Session = Depends(get_db),
) -> RecommendationResponse:
    svc = RecommendationService(db)
    result = svc.recommend(session_id, limit=limit)
    return RecommendationResponse(**result)