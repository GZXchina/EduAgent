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
    """星火未配置时的规则兜底，便于本地开发与演示。
    通用化设计，不绑定特定学科/编程语言。
    """
    level = "beginner"
    if any(w in text for w in ("熟练", "进阶", "高级", "有经验", "精通")):
        level = "advanced"
    elif any(w in text for w in ("学过", "基础", "中等", "中级", "有一定基础")):
        level = "intermediate"

    style = "reading"
    if any(w in text for w in ("图解", "图像", "看图", "视觉", "思维导图")):
        style = "visual"
    elif any(w in text for w in ("听讲", "音频", "听课", "讲解")):
        style = "auditory"
    elif any(w in text for w in ("动手", "实践", "实验", "实操", "项目")):
        style = "kinesthetic"

    goal = "general_learning"
    if any(w in text for w in ("蓝桥", "竞赛", "比赛", "ACM")):
        goal = "lanqiao_competition"
    elif any(w in text for w in ("考研", "研究生", "初试", "复试")):
        goal = "postgraduate_exam"
    elif any(w in text for w in ("就业", "求职", "面试", "找工作", "实习")):
        goal = "job_preparation"
    elif any(w in text for w in ("证书", "考试", "认证", "资格证")):
        goal = "certification"
    elif any(w in text for w in ("研究", "论文", "学术")):
        goal = "research"

    # 通用薄弱点提取：从用户输入中识别"不会/不懂/薄弱/难"等关键词后面的内容
    weakness = ""
    weakness_patterns = [
        r"不会[的是]?(.{2,6})",
        r"不懂[的是]?(.{2,6})",
        r"薄弱[点是]?(.{2,6})",
        r"难[以的点]?[的是]?(.{2,6})",
        r"掌握不好[的是]?(.{2,6})",
    ]
    for pattern in weakness_patterns:
        m = re.search(pattern, text)
        if m:
            weakness = m.group(1).strip().rstrip("，。,. ")
            break
    # 回退：常见学科关键词（通用列表，不局限于编程）
    if not weakness:
        common_keywords = [
            "循环", "函数", "面向对象", "指针", "递归", "数组",
            "微积分", "线性代数", "概率", "统计",
            "语法", "写作", "阅读理解", "听力",
            "有机化学", "无机化学", "物理", "力学",
            "数据结构", "算法", "操作系统", "网络",
        ]
        for kw in common_keywords:
            if kw in text:
                weakness = kw
                break

    # 学习时间提取（通用模式）
    study_time = "unknown"
    m = re.search(r"每天\s*(\d+)\s*[小时h]", text)
    if m:
        study_time = f"{m.group(1)}h/day"
    elif re.search(r"每周\s*(\d+)\s*[小时h]", text):
        m2 = re.search(r"每周\s*(\d+)\s*[小时h]", text)
        if m2:
            weekly = int(m2.group(1))
            study_time = f"{max(1, weekly // 7)}h/day"
    elif any(w in text for w in ("1小时", "一小时", "一小时左右")):
        study_time = "1h/day"
    elif any(w in text for w in ("2小时", "两小时", "两个小时")):
        study_time = "2h/day"

    # 通用专业/学科提取：从用户输入中识别专业名称
    major = ""
    major_patterns = [
        r"专业[是为]?([\u4e00-\u9fa5]{2,8})",
        r"学[的是习]([\u4e00-\u9fa5]{2,8})",
        r"([\u4e00-\u9fa5]{2,6})专业",
    ]
    for pattern in major_patterns:
        m = re.search(pattern, text)
        if m:
            candidate = m.group(1).strip()
            # 过滤掉过于通用的词
            if candidate not in ("好", "的", "很", "一些", "什么", "很多"):
                major = candidate
                break

    # 如果专业字段为空，尝试从学习目标中提取主题
    learning_goal_text = text[:200]

    return StudentProfile(
        knowledge_level=level,
        learning_style=style,
        weakness=weakness,
        goal=goal,
        study_time=study_time,
        major=major,
        learning_goal_text=learning_goal_text,
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
