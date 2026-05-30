from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from backend.core.redis_client import RedisClient
from backend.integrations.spark.client import SparkClient, get_spark_client
from backend.settings import get_settings
from database.repository import ProfileRepository
from schemas.profile import StudentProfile

logger = logging.getLogger(__name__)

PROFILE_CACHE_PREFIX = "eduagent:profile:"


def _prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts" / "profile_agent.md"


def load_profile_prompt() -> str:
    path = _prompt_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "你是学生画像分析助手，仅输出 JSON。"


def heuristic_profile(text: str) -> StudentProfile:
    """星火未配置时的规则兜底，便于本地开发与演示。"""
    t = text.lower()
    level = "beginner"
    if any(w in text for w in ("熟练", "进阶", "高级", "有经验")):
        level = "advanced"
    elif any(w in text for w in ("学过", "基础", "中等", "中级")):
        level = "intermediate"

    style = "reading"
    if any(w in text for w in ("图解", "图像", "看图", "视觉")):
        style = "visual"
    elif any(w in text for w in ("听讲", "音频", "听课")):
        style = "auditory"
    elif any(w in text for w in ("动手", "实践", "实验")):
        style = "kinesthetic"

    goal = "general_learning"
    if "蓝桥" in text:
        goal = "lanqiao_competition"
    elif any(w in text for w in ("考研", "研究生")):
        goal = "postgraduate_exam"
    elif any(w in text for w in ("就业", "求职", "面试")):
        goal = "job_preparation"

    weakness = ""
    for kw in ("循环", "函数", "面向对象", "指针", "递归", "数组"):
        if kw in text:
            weakness = kw
            break

    study_time = "unknown"
    m = re.search(r"每天\s*(\d+)\s*小时", text)
    if m:
        study_time = f"{m.group(1)}h/day"
    elif "1小时" in text or "一小时" in text:
        study_time = "1h/day"

    major = ""
    if "计算机" in text:
        major = "计算机科学"
    elif "软件" in text:
        major = "软件工程"

    return StudentProfile(
        knowledge_level=level,
        learning_style=style,
        weakness=weakness,
        goal=goal,
        study_time=study_time,
        major=major,
        learning_goal_text=text[:200],
        learning_base="初学" if level == "beginner" else "有基础",
        learning_style_text=style,
        raw_input=text,
    )


class ProfileService:
    def __init__(
        self,
        db: Session,
        redis: RedisClient,
        spark: SparkClient | None = None,
    ) -> None:
        self.db = db
        self.redis = redis
        self.spark = spark or get_spark_client()
        self.repo = ProfileRepository(db)
        self.settings = get_settings()

    def _cache_key(self, session_id: str) -> str:
        return f"{PROFILE_CACHE_PREFIX}{session_id}"

    def get_cached(self, session_id: str) -> StudentProfile | None:
        data = self.redis.get_json(self._cache_key(session_id))
        if data:
            return StudentProfile.model_validate(data)
        row = self.repo.get_by_session(session_id)
        if row:
            return StudentProfile.model_validate(ProfileRepository.to_dict(row))
        return None

    def _save(self, session_id: str, profile: StudentProfile) -> None:
        payload = profile.model_dump()
        self.repo.upsert(session_id, payload)
        self.redis.set_json(
            self._cache_key(session_id),
            payload,
            ex=self.settings.profile_cache_ttl,
        )

    async def build_profile(
        self,
        message: str,
        session_id: str | None = None,
        *,
        use_cache: bool = True,
    ) -> tuple[StudentProfile, str]:
        sid = session_id or str(uuid.uuid4())[:16]

        if use_cache:
            cached = self.get_cached(sid)
            if cached and cached.raw_input == message:
                return cached, "cache"

        source = "heuristic"
        if self.spark.configured:
            try:
                profile = await self._build_with_spark(message)
                source = "spark"
            except Exception as exc:
                logger.warning("星火画像失败，使用规则兜底: %s", exc)
                profile = heuristic_profile(message)
        else:
            profile = heuristic_profile(message)

        self._save(sid, profile)
        return profile, source

    async def _build_with_spark(self, message: str) -> StudentProfile:
        system_prompt = load_profile_prompt()
        user_prompt = (
            f"请分析以下学生学习描述，输出严格 JSON（不要其它说明）：\n\n{message}\n\n"
            "JSON 字段：knowledge_level, learning_style, weakness, goal, study_time, "
            "major, learning_goal_text, learning_base, learning_style_text"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        data = await self.spark.chat_json(messages)
        profile = StudentProfile.from_llm_dict(data, raw_input=message)
        return profile
