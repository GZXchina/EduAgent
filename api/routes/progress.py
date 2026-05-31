from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.deps import get_db
from database.repository import ProfileRepository, ResourceRepository

router = APIRouter(prefix="/api/progress", tags=["progress"])


class ResourceStats(BaseModel):
    total: int
    by_type: dict[str, int]


class EvaluationStats(BaseModel):
    total_reports: int
    latest_score: float | None = None
    latest_level: str | None = None


class ProgressResponse(BaseModel):
    session_id: str
    profile_exists: bool
    resources: ResourceStats
    evaluation: EvaluationStats
    updated_at: str | None = None


def _score_to_level(score: float) -> str:
    if score >= 90:
        return "优秀"
    if score >= 75:
        return "良好"
    if score >= 60:
        return "中等"
    return "需改进"


@router.get("/{session_id}", response_model=ProgressResponse)
async def get_progress(
    session_id: str,
    db: Session = Depends(get_db),
) -> ProgressResponse:
    profile_repo = ProfileRepository(db)
    resource_repo = ResourceRepository(db)

    # Profile
    profile_row = profile_repo.get_by_session(session_id)
    profile_exists = profile_row is not None
    profile_updated_at = profile_row.updated_at if profile_row else None

    # Resources
    resource_rows = resource_repo.get_resources_by_session(session_id)
    by_type: dict[str, int] = {}
    for row in resource_rows:
        by_type[row.resource_type] = by_type.get(row.resource_type, 0) + 1

    # Evaluation
    report_rows = resource_repo.get_evaluation_reports(session_id)
    total_reports = len(report_rows)
    latest_score = None
    latest_level = None
    if report_rows:
        latest_score = report_rows[0].score
        if latest_score is not None:
            latest_level = _score_to_level(latest_score)

    # Determine updated_at: use the most recent timestamp among profile and reports
    updated_at = None
    candidates: list[datetime] = []
    if profile_updated_at:
        candidates.append(profile_updated_at)
    if report_rows:
        report_time = report_rows[0].created_at
        if report_time:
            candidates.append(report_time)
    if resource_rows:
        resource_time = resource_rows[0].created_at
        if resource_time:
            candidates.append(resource_time)
    if candidates:
        updated_at = max(candidates).isoformat()

    return ProgressResponse(
        session_id=session_id,
        profile_exists=profile_exists,
        resources=ResourceStats(total=len(resource_rows), by_type=by_type),
        evaluation=EvaluationStats(
            total_reports=total_reports,
            latest_score=latest_score,
            latest_level=latest_level,
        ),
        updated_at=updated_at,
    )