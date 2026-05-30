from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.deps import get_app_settings, get_db, get_redis_client
from backend.core.redis_client import RedisClient
from backend.settings import Settings

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health(
    settings: Settings = Depends(get_app_settings),
) -> dict:
    return {
        "status": "ok",
        "env": settings.app_env,
        "spark": "configured" if settings.spark_configured else "not_configured",
        "spark_mode": settings.spark_api_type if settings.spark_configured else None,
        "embedding_model": settings.embedding_model,
    }


@router.get("/health/detailed")
async def health_detailed(
    settings: Settings = Depends(get_app_settings),
    redis: RedisClient = Depends(get_redis_client),
    db: Session = Depends(get_db),
) -> dict:
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_status = str(exc)
    else:
        db_status = "ok"

    return {
        "status": "ok" if db_ok else "degraded",
        "env": settings.app_env,
        "database": db_status,
        "redis": "ok" if redis.available else "unavailable (memory fallback)",
        "spark": "configured" if settings.spark_configured else "not_configured",
        "spark_mode": settings.spark_api_type if settings.spark_configured else None,
        "spark_domain": settings.spark_domain if settings.spark_configured else None,
        "embedding_model": settings.embedding_model,
        "chroma_dir": settings.chroma_persist_dir,
    }