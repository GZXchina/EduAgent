from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.deps import get_db, get_redis_client
from backend.core.redis_client import RedisClient
from backend.integrations.spark.client import get_spark_client
from schemas.profile import ProfileBuildRequest, ProfileResponse, StudentProfile
from services.profile_service import ProfileService

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _service(db: Session, redis: RedisClient) -> ProfileService:
    return ProfileService(db, redis, get_spark_client())


@router.post("/build", response_model=ProfileResponse)
async def build_profile(
    body: ProfileBuildRequest,
    db: Session = Depends(get_db),
    redis: RedisClient = Depends(get_redis_client),
) -> ProfileResponse:
    sid = body.session_id or str(uuid.uuid4())[:16]
    svc = _service(db, redis)
    profile, source = await svc.build_profile(body.message, sid, use_cache=False)
    return ProfileResponse(session_id=sid, profile=profile, source=source, cached=False)


@router.get("/{session_id}", response_model=ProfileResponse)
async def get_profile(
    session_id: str,
    db: Session = Depends(get_db),
    redis: RedisClient = Depends(get_redis_client),
) -> ProfileResponse:
    svc = _service(db, redis)
    profile = svc.get_cached(session_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="未找到该会话的学生画像")
    return ProfileResponse(session_id=session_id, profile=profile, source="stored", cached=True)


@router.post("/analyze", response_model=ProfileResponse)
async def analyze_profile(
    body: ProfileBuildRequest,
    db: Session = Depends(get_db),
    redis: RedisClient = Depends(get_redis_client),
) -> ProfileResponse:
    """对话式分析：无 session_id 时自动生成。"""
    sid = body.session_id or str(uuid.uuid4())[:16]
    svc = _service(db, redis)
    profile, source = await svc.build_profile(body.message, sid)
    return ProfileResponse(session_id=sid, profile=profile, source=source)
