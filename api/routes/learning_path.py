from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.deps import get_db
from services.learning_path_service import LearningPathService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/learning-path", tags=["learning-path"])


class LearningPathGenerateRequest(BaseModel):
    session_id: str = Field(..., min_length=1, description="会话标识")


class StepResource(BaseModel):
    resource_type: str
    resource_label: str
    resource_icon: str
    topic: str
    preview: str
    id: int


class StepWithResources(BaseModel):
    week: int
    title: str
    duration: str
    topics: list[str]
    recommended_resource_types: list[str]
    assessment: str
    available_resources: list[dict[str, Any]]


class LearningPathOverview(BaseModel):
    path_name: str
    total_weeks: int
    focus_areas: list[str]
    suggestions: list[str]
    source: str


class LearningPathResponse(BaseModel):
    session_id: str
    profile_found: bool
    profile_summary: str | None = None
    message: str | None = None
    learning_path: LearningPathOverview | None = None
    steps_with_resources: list[dict[str, Any]] = []
    total_available_resources: int = 0
    total_steps: int = 0


@router.post("/generate", response_model=LearningPathResponse)
async def generate_learning_path(
    body: LearningPathGenerateRequest,
    db: Session = Depends(get_db),
) -> LearningPathResponse:
    svc = LearningPathService(db)
    result = await svc.generate_learning_path(body.session_id)
    return LearningPathResponse(**result)


@router.get("/{session_id}", response_model=LearningPathResponse)
async def get_learning_path(
    session_id: str,
    db: Session = Depends(get_db),
) -> LearningPathResponse:
    svc = LearningPathService(db)
    result = await svc.generate_learning_path(session_id)
    return LearningPathResponse(**result)