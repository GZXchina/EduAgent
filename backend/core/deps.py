from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from backend.core.redis_client import RedisClient, get_redis
from backend.settings import Settings, get_settings
from database.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_app_settings() -> Settings:
    return get_settings()


def get_redis_client() -> RedisClient:
    return get_redis()
