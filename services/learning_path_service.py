from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from agents.planner_agent import PlannerAgent, heuristic_path
from database.repository import ProfileRepository, ResourceRepository
from schemas.profile import LearningPath, LearningStep, StudentProfile

logger = logging.getLogger(__name__)

TOPIC_RESOURCE_MAP: dict[str, list[str]] = {
    "Python环境搭建": ["ppt", "video"],
    "变量与数据类型": ["ppt", "quiz", "code"],
    "基本输入输出": ["code", "quiz"],
    "条件语句": ["code", "quiz"],
    "循环结构": ["code", "quiz", "mindmap"],
    "函数定义与调用": ["ppt", "code", "quiz"],
    "列表与字典": ["code", "quiz", "mindmap"],
    "字符串操作": ["code", "quiz"],
    "文件操作": ["code", "ppt"],
    "异常处理": ["code", "quiz"],
    "面向对象编程": ["ppt", "code", "mindmap"],
    "模块与包": ["ppt", "code"],
    "装饰器": ["code", "ppt"],
    "生成器与迭代器": ["code", "mindmap"],
    "lambda表达式": ["code", "quiz"],
    "标准库使用": ["code", "ppt"],
    "正则表达式": ["code", "quiz"],
    "JSON处理": ["code", "ppt"],
    "算法基础": ["ppt", "mindmap", "quiz"],
    "数据结构": ["ppt", "mindmap", "code"],
    "时间复杂度分析": ["ppt", "quiz"],
    "递归": ["code", "mindmap"],
    "动态规划入门": ["code", "quiz"],
    "图论基础": ["ppt", "mindmap"],
    "蓝桥杯真题": ["quiz", "code"],
    "模拟比赛": ["quiz", "code"],
}

RESOURCE_LABELS: dict[str, str] = {
    "ppt": "PPT课件",
    "quiz": "题库练习",
    "code": "代码案例",
    "mindmap": "思维导图",
    "video": "视频脚本",
}

RESOURCE_ICONS: dict[str, str] = {
    "ppt": "📊",
    "quiz": "📝",
    "code": "💻",
    "mindmap": "🧠",
    "video": "🎬",
}


class LearningPathService:

    def __init__(self, db: Session) -> None:
        self.db = db
        self.profile_repo = ProfileRepository(db)
        self.resource_repo = ResourceRepository(db)
        self.planner = PlannerAgent()

    def get_profile(self, session_id: str) -> StudentProfile | None:
        row = self.profile_repo.get_by_session(session_id)
        if row is None:
            return None
        data = ProfileRepository.to_dict(row)
        return StudentProfile.model_validate(data)

    def get_available_resources(
        self, session_id: str
    ) -> list[dict[str, Any]]:
        rows = self.resource_repo.get_resources_by_session(session_id)
        resources = []
        for row in rows:
            content = ResourceRepository.resource_to_dict(row)
            resources.append({
                "id": row.id,
                "resource_type": row.resource_type,
                "resource_label": RESOURCE_LABELS.get(row.resource_type, row.resource_type),
                "resource_icon": RESOURCE_ICONS.get(row.resource_type, "📄"),
                "topic": content.get("topic", ""),
                "content": content,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })
        return resources

    def match_resources_to_steps(
        self,
        steps: list[LearningStep],
        resources: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        steps_with_resources = []
        for step in steps:
            step_resources = []
            for topic in step.topics:
                for resource in resources:
                    if resource["topic"] and topic in resource["topic"]:
                        if resource["id"] not in [r["id"] for r in step_resources]:
                            step_resources.append(resource)

            if not step_resources:
                for resource_type in TOPIC_RESOURCE_MAP.get(step.topics[0] if step.topics else "", []):
                    for resource in resources:
                        if resource["resource_type"] == resource_type:
                            if resource["id"] not in [r["id"] for r in step_resources]:
                                step_resources.append(resource)
                                break

            steps_with_resources.append({
                "week": step.week,
                "title": step.title,
                "duration": step.duration,
                "topics": step.topics,
                "recommended_resource_types": step.resources,
                "assessment": step.assessment,
                "available_resources": step_resources[:4],
            })

        return steps_with_resources

    async def generate_learning_path(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        profile = self.get_profile(session_id)
        if profile is None:
            return {
                "session_id": session_id,
                "profile_found": False,
                "message": "未找到学生画像，请先完成画像分析",
                "learning_path": None,
                "steps_with_resources": [],
            }

        learning_path, source = await self.planner._generate_path(profile)
        resources = self.get_available_resources(session_id)
        steps_with_resources = self.match_resources_to_steps(learning_path.steps, resources)

        logger.info(
            "学习路径生成: session=%s, path=%s, weeks=%d, steps=%d, resources=%d, source=%s",
            session_id,
            learning_path.path_name,
            learning_path.total_weeks,
            len(steps_with_resources),
            len(resources),
            source,
        )

        return {
            "session_id": session_id,
            "profile_found": True,
            "profile_summary": self._profile_summary(profile),
            "learning_path": {
                "path_name": learning_path.path_name,
                "total_weeks": learning_path.total_weeks,
                "focus_areas": learning_path.focus_areas,
                "suggestions": learning_path.suggestions,
                "source": source,
            },
            "steps_with_resources": steps_with_resources,
            "total_available_resources": len(resources),
            "total_steps": len(steps_with_resources),
        }

    @staticmethod
    def _profile_summary(profile: StudentProfile) -> str:
        return (
            f"专业={profile.major or '未填'} | "
            f"水平={profile.knowledge_level} | "
            f"风格={profile.learning_style} | "
            f"目标={profile.goal} | "
            f"薄弱={profile.weakness or '待发现'}"
        )