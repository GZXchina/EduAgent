from __future__ import annotations

import uuid
from typing import Any

from agents.base import BaseAgent
from backend.core.redis_client import get_redis
from database.session import SessionLocal
from services.profile_service import ProfileService


class ProfileAgent(BaseAgent):
    """学生画像 Agent：星火分析 + PostgreSQL/SQLite + Redis 缓存。"""

    name = "profile"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        text = state.get("user_input", "")
        session_id = state.get("session_id") or str(uuid.uuid4())[:16]

        db = SessionLocal()
        try:
            svc = ProfileService(db, get_redis())
            profile, source = await svc.build_profile(text, session_id)
            payload = profile.model_dump()
        finally:
            db.close()

        summary = (
            f"【学生画像】专业={profile.major or '未填'} | "
            f"水平={profile.knowledge_level} | 风格={profile.learning_style} | "
            f"目标={profile.goal} | 薄弱={profile.weakness or '待发现'} | "
            f"时长={profile.study_time}（来源: {source}）"
        )
        return {
            "session_id": session_id,
            "student_profile": payload,
            "messages": [{"role": "assistant", "content": summary}],
        }
