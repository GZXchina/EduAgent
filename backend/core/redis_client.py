from __future__ import annotations

import json
import logging
from typing import Any

from backend.settings import get_settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis 封装；不可用时降级为内存字典，不阻断主流程。"""

    def __init__(self) -> None:
        self._client: Any = None
        self._memory: dict[str, str] = {}
        self._available = False
        settings = get_settings()
        if not settings.redis_enabled:
            return
        try:
            import redis

            self._client = redis.from_url(settings.redis_url, decode_responses=True)
            self._client.ping()
            self._available = True
            logger.info("Redis 已连接: %s", settings.redis_url)
        except Exception as exc:
            logger.warning("Redis 不可用，使用内存缓存: %s", exc)

    @property
    def available(self) -> bool:
        return self._available

    def get(self, key: str) -> str | None:
        if self._available and self._client:
            return self._client.get(key)
        return self._memory.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        if self._available and self._client:
            self._client.set(key, value, ex=ex)
            return
        self._memory[key] = value

    def get_json(self, key: str) -> Any | None:
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def set_json(self, key: str, value: Any, ex: int | None = None) -> None:
        self.set(key, json.dumps(value, ensure_ascii=False), ex=ex)

    def delete(self, key: str) -> None:
        if self._available and self._client:
            self._client.delete(key)
        self._memory.pop(key, None)


_redis: RedisClient | None = None


def get_redis() -> RedisClient:
    global _redis
    if _redis is None:
        _redis = RedisClient()
    return _redis
