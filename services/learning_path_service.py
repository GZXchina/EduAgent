from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from agents.planner_agent import PlannerAgent, heuristic_path
from database.repository import ProfileRepository, ResourceRepository
from schemas.profile import LearningPath, LearningStep, StudentProfile

logger = logging.getLogger(__name__)

# 通用资源类型推荐策略：根据学习步骤的位置和内容特征推荐资源类型
# 不再硬编码特定学科主题，而是通过步骤位置和关键词匹配
_STAGE_RESOURCE_MAP: dict[str, list[str]] = {
    "入门": ["ppt", "video", "mindmap"],
    "概述": ["ppt", "video", "mindmap"],
    "基础": ["ppt", "quiz", "mindmap"],
    "概念": ["ppt", "mindmap", "video"],
    "操作": ["code", "quiz"],
    "实践": ["code", "quiz", "video"],
    "应用": ["code", "quiz", "ppt"],
    "进阶": ["ppt", "code", "mindmap"],
    "深入": ["ppt", "code", "quiz"],
    "高级": ["code", "ppt", "mindmap"],
    "项目": ["code", "ppt", "video"],
    "综合": ["ppt", "quiz", "code", "mindmap"],
    "评估": ["quiz", "code"],
    "冲刺": ["quiz", "code"],
    "真题": ["quiz", "code"],
    "模拟": ["quiz", "code"],
    "面试": ["quiz", "ppt"],
}
# 默认推荐：所有资源类型轮转
_DEFAULT_RESOURCE_TYPES: list[list[str]] = [
    ["ppt", "mindmap"],
    ["code", "quiz"],
    ["video", "ppt"],
    ["mindmap", "code"],
    ["quiz", "video"],
]

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
                # 通用推荐：根据步骤标题关键词匹配资源类型
                recommended_types: list[str] = []
                step_text = step.title + " ".join(step.topics)
                for keyword, types in _STAGE_RESOURCE_MAP.items():
                    if keyword in step_text:
                        recommended_types.extend(types)
                        break

                # 如果标题没有匹配任何关键词，按步骤位置轮转推荐
                if not recommended_types:
                    idx = (step.week - 1) % len(_DEFAULT_RESOURCE_TYPES)
                    recommended_types = _DEFAULT_RESOURCE_TYPES[idx]

                # 去重并保留顺序
                seen: set[str] = set()
                unique_types: list[str] = []
                for rt in recommended_types:
                    if rt not in seen:
                        seen.add(rt)
                        unique_types.append(rt)

                for resource_type in unique_types:
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