from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from database.repository import ProfileRepository, ResourceRepository
from schemas.profile import StudentProfile

logger = logging.getLogger(__name__)

STYLE_RESOURCE_MAP: dict[str, list[str]] = {
    "visual": ["mindmap", "ppt", "video"],
    "auditory": ["video", "ppt"],
    "reading": ["ppt", "quiz", "code"],
    "kinesthetic": ["code", "quiz"],
}

GOAL_RESOURCE_PRIORITY: dict[str, list[str]] = {
    "lanqiao_competition": ["code", "quiz", "mindmap"],
    "postgraduate_exam": ["ppt", "mindmap", "quiz"],
    "job_preparation": ["code", "ppt", "quiz"],
    "general_learning": ["ppt", "mindmap", "quiz", "code", "video"],
}

RESOURCE_LABELS: dict[str, str] = {
    "ppt": "PPT课件",
    "quiz": "题库练习",
    "code": "代码案例",
    "mindmap": "思维导图",
    "video": "视频脚本",
}

LEVEL_SCORES: dict[str, int] = {
    "beginner": 25,
    "intermediate": 55,
    "advanced": 85,
}


def _extract_topic_from_resource(resource_type: str, content: dict[str, Any]) -> str:
    if resource_type == "ppt" and content.get("topic"):
        return str(content["topic"])
    if resource_type == "quiz" and content.get("topic"):
        return str(content["topic"])
    if resource_type == "code" and content.get("topic"):
        return str(content["topic"])
    if resource_type == "mindmap" and content.get("topic"):
        return str(content["topic"])
    return ""


def _extract_preview(resource_type: str, content: dict[str, Any]) -> str:
    if resource_type == "ppt" and content.get("slides"):
        slides = content["slides"]
        if isinstance(slides, list) and slides:
            return str(slides[0].get("title", content.get("topic", "")))
    if resource_type == "quiz" and content.get("questions"):
        questions = content["questions"]
        if isinstance(questions, list):
            return f"共{len(questions)}道题目"
    if resource_type == "code" and content.get("examples"):
        examples = content["examples"]
        if isinstance(examples, list):
            return f"共{len(examples)}个代码示例"
    if resource_type == "mindmap":
        return "知识结构图"
    if resource_type == "video" and content.get("scenes"):
        scenes = content["scenes"]
        if isinstance(scenes, list):
            return f"共{len(scenes)}个场景"
    return ""


class RecommendationService:

    def __init__(self, db: Session) -> None:
        self.db = db
        self.profile_repo = ProfileRepository(db)
        self.resource_repo = ResourceRepository(db)

    def get_profile(self, session_id: str) -> StudentProfile | None:
        row = self.profile_repo.get_by_session(session_id)
        if row is None:
            return None
        data = ProfileRepository.to_dict(row)
        return StudentProfile.model_validate(data)

    def get_candidate_resources(
        self, session_id: str
    ) -> list[tuple[str, dict[str, Any], int]]:
        rows = self.resource_repo.get_resources_by_session(session_id)
        candidates: list[tuple[str, dict[str, Any], int]] = []
        for row in rows:
            content = ResourceRepository.resource_to_dict(row)
            candidates.append((row.resource_type, content, row.id))
        return candidates

    def calculate_relevance(
        self,
        profile: StudentProfile,
        resource_type: str,
        content: dict[str, Any],
    ) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []

        topic = _extract_topic_from_resource(resource_type, content)

        if profile.weakness and topic and profile.weakness in topic:
            score += 30
            reasons.append(f"覆盖薄弱点「{profile.weakness}」")

        style_resources = STYLE_RESOURCE_MAP.get(profile.learning_style, [])
        if resource_type in style_resources:
            score += 25
            style_label = {"visual": "视觉型", "auditory": "听觉型", "reading": "阅读型", "kinesthetic": "动手型"}.get(
                profile.learning_style, profile.learning_style
            )
            reasons.append(f"匹配{style_label}学习风格")

        goal_priority = GOAL_RESOURCE_PRIORITY.get(profile.goal, [])
        if resource_type in goal_priority:
            priority_index = goal_priority.index(resource_type)
            score += max(20 - priority_index * 5, 5)
            reasons.append(f"符合「{profile.goal}」学习目标")

        level_score = LEVEL_SCORES.get(profile.knowledge_level, 30)
        resource_count = 0
        if resource_type == "quiz" and content.get("questions"):
            resource_count = len(content["questions"])
        elif resource_type == "code" and content.get("examples"):
            resource_count = len(content["examples"])
        elif resource_type == "ppt" and content.get("slides"):
            resource_count = len(content["slides"])
        if resource_count > 0:
            score += min(resource_count, 10)
            reasons.append(f"内容丰富({resource_count}项)")

        if level_score < 40 and resource_type in ("ppt", "mindmap"):
            score += 10
            reasons.append("适合初学者水平")
        elif level_score >= 70 and resource_type in ("code", "quiz"):
            score += 10
            reasons.append("适合进阶提升")

        return score, reasons

    def recommend(
        self,
        session_id: str,
        limit: int = 6,
    ) -> dict[str, Any]:
        profile = self.get_profile(session_id)
        if profile is None:
            return {
                "session_id": session_id,
                "profile_found": False,
                "message": "未找到学生画像，请先完成画像构建",
                "recommendations": [],
            }

        candidates = self.get_candidate_resources(session_id)
        if not candidates:
            return {
                "session_id": session_id,
                "profile_found": True,
                "profile_summary": self._profile_summary(profile),
                "message": "暂无资源，请先生成学习资源",
                "recommendations": [],
            }

        scored: list[dict[str, Any]] = []
        for resource_type, content, resource_id in candidates:
            score, reasons = self.calculate_relevance(profile, resource_type, content)
            scored.append({
                "id": resource_id,
                "resource_type": resource_type,
                "resource_label": RESOURCE_LABELS.get(resource_type, resource_type),
                "topic": _extract_topic_from_resource(resource_type, content),
                "preview": _extract_preview(resource_type, content),
                "relevance_score": score,
                "reasons": reasons,
                "content": content,
            })

        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        top = scored[:limit]

        logger.info(
            "推荐引擎: session=%s, 候选=%d, 推荐=%d, 画像=%s",
            session_id,
            len(scored),
            len(top),
            self._profile_summary(profile),
        )

        return {
            "session_id": session_id,
            "profile_found": True,
            "profile_summary": self._profile_summary(profile),
            "total_resources": len(scored),
            "recommendations": top,
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