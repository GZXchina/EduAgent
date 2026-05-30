from __future__ import annotations

import logging
from typing import Any

from schemas.profile import StudentProfile

logger = logging.getLogger(__name__)


class LearningBehaviorData:
    """学习行为数据结构。"""

    def __init__(
        self,
        study_duration_minutes: int = 0,
        quiz_results: list[dict[str, Any]] | None = None,
        knowledge_mastery: dict[str, float] | None = None,
        resource_usage: dict[str, int] | None = None,
    ) -> None:
        self.study_duration_minutes = study_duration_minutes
        self.quiz_results = quiz_results or []
        self.knowledge_mastery = knowledge_mastery or {}
        self.resource_usage = resource_usage or {
            "ppt": 0,
            "quiz": 0,
            "code": 0,
            "mindmap": 0,
            "video": 0,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "study_duration_minutes": self.study_duration_minutes,
            "quiz_results": self.quiz_results,
            "knowledge_mastery": self.knowledge_mastery,
            "resource_usage": self.resource_usage,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LearningBehaviorData":
        return cls(
            study_duration_minutes=data.get("study_duration_minutes", 0),
            quiz_results=data.get("quiz_results", []),
            knowledge_mastery=data.get("knowledge_mastery", {}),
            resource_usage=data.get("resource_usage", {}),
        )


class EvaluationMetrics:
    """评估指标计算器。"""

    @staticmethod
    def calculate_quiz_accuracy(quiz_results: list[dict[str, Any]]) -> float:
        """计算练习正确率。"""
        if not quiz_results:
            return 0.0
        correct = sum(1 for r in quiz_results if r.get("correct", False))
        return (correct / len(quiz_results)) * 100

    @staticmethod
    def calculate_knowledge_mastery_score(knowledge_mastery: dict[str, float]) -> float:
        """计算知识掌握度得分。"""
        if not knowledge_mastery:
            return 0.0
        return sum(knowledge_mastery.values()) / len(knowledge_mastery)

    @staticmethod
    def calculate_resource_utilization(resource_usage: dict[str, int]) -> float:
        """计算资源利用率。"""
        if not resource_usage:
            return 0.0
        total = sum(resource_usage.values())
        if total == 0:
            return 0.0
        engaged = sum(1 for v in resource_usage.values() if v > 0)
        return (engaged / len(resource_usage)) * 100

    @staticmethod
    def calculate_study_dedication_score(duration_minutes: int, target_minutes_per_day: int = 60) -> float:
        """计算学习投入度得分。"""
        if duration_minutes <= 0:
            return 0.0
        target = target_minutes_per_day * 7
        ratio = min(duration_minutes / target, 1.0)
        return ratio * 100


class EvaluationService:
    """学习评估服务：分析学习行为数据生成评估报告。"""

    def __init__(self) -> None:
        self.metrics = EvaluationMetrics()

    def analyze_behavior(self, behavior: LearningBehaviorData) -> dict[str, Any]:
        """分析学习行为数据。"""
        quiz_accuracy = self.metrics.calculate_quiz_accuracy(behavior.quiz_results)
        knowledge_mastery_score = self.metrics.calculate_knowledge_mastery_score(behavior.knowledge_mastery)
        resource_utilization = self.metrics.calculate_resource_utilization(behavior.resource_usage)
        dedication_score = self.metrics.calculate_study_dedication_score(behavior.study_duration_minutes)

        return {
            "quiz_accuracy": round(quiz_accuracy, 1),
            "knowledge_mastery_score": round(knowledge_mastery_score, 1),
            "resource_utilization": round(resource_utilization, 1),
            "dedication_score": round(dedication_score, 1),
        }

    def calculate_comprehensive_score(self, behavior: LearningBehaviorData) -> int:
        """计算综合评分(0-100)。"""
        analysis = self.analyze_behavior(behavior)

        weights = {
            "quiz_accuracy": 0.3,
            "knowledge_mastery_score": 0.3,
            "resource_utilization": 0.2,
            "dedication_score": 0.2,
        }

        score = sum(analysis[key] * weight for key, weight in weights.items())
        return int(min(max(score, 0), 100))

    def determine_level(self, score: int) -> str:
        """根据评分确定等级。"""
        if score >= 90:
            return "优秀"
        elif score >= 75:
            return "良好"
        elif score >= 60:
            return "中等"
        else:
            return "需加强"

    def generate_strengths_and_weaknesses(
        self, behavior: LearningBehaviorData, analysis: dict[str, Any]
    ) -> tuple[list[str], list[str]]:
        """分析优势与薄弱点。"""
        strengths: list[str] = []
        weaknesses: list[str] = []

        if analysis["quiz_accuracy"] >= 80:
            strengths.append("练习正确率高，掌握情况良好")
        elif analysis["quiz_accuracy"] < 50:
            weaknesses.append("练习正确率偏低，需要加强练习")

        if analysis["knowledge_mastery_score"] >= 70:
            strengths.append("知识掌握扎实")
        elif analysis["knowledge_mastery_score"] < 40:
            weaknesses.append("部分知识点掌握不足")

        if analysis["resource_utilization"] >= 60:
            strengths.append("资源利用率高，学习积极")
        elif analysis["resource_utilization"] < 30:
            weaknesses.append("资源利用不充分，建议多使用学习资源")

        if analysis["dedication_score"] >= 70:
            strengths.append("学习投入度高")
        elif analysis["dedication_score"] < 40:
            weaknesses.append("学习时间不足，建议增加学习时长")

        return strengths, weaknesses

    def generate_suggestions(
        self,
        profile: StudentProfile,
        behavior: LearningBehaviorData,
        analysis: dict[str, Any],
        strengths: list[str],
        weaknesses: list[str],
    ) -> list[str]:
        """生成学习建议。"""
        suggestions: list[str] = []

        if analysis["quiz_accuracy"] < 60:
            suggestions.append("建议针对错题进行专项练习")
            suggestions.append("可以观看视频教程加深理解")

        if analysis["knowledge_mastery_score"] < 50:
            suggestions.append("建议重新学习薄弱知识点")
            suggestions.append("使用思维导图梳理知识结构")

        if analysis["resource_utilization"] < 50:
            suggestions.append("建议充分利用各类学习资源")

        if analysis["dedication_score"] < 50:
            suggestions.append("建议每天保持1小时以上的学习时间")

        if profile.weakness:
            suggestions.append(f"重点加强: {profile.weakness}")

        if not suggestions:
            suggestions.append("继续保持当前学习节奏")
            suggestions.append("可以尝试挑战更高难度的练习")

        return suggestions[:5]

    def generate_report(self, profile: StudentProfile, behavior: LearningBehaviorData) -> dict[str, Any]:
        """生成完整的学习评估报告。"""
        analysis = self.analyze_behavior(behavior)
        score = self.calculate_comprehensive_score(behavior)
        level = self.determine_level(score)
        strengths, weaknesses = self.generate_strengths_and_weaknesses(behavior, analysis)
        suggestions = self.generate_suggestions(profile, behavior, analysis, strengths, weaknesses)

        if score >= 90:
            comment = "学习表现非常出色！继续保持！"
        elif score >= 75:
            comment = "学习效果不错，可以继续深入！"
        elif score >= 60:
            comment = "基本掌握了内容，建议多做练习。"
        else:
            comment = "需要更多练习来巩固知识。"

        return {
            "score": score,
            "level": level,
            "comment": comment,
            "analysis": analysis,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "suggestions": suggestions,
            "evaluated": True,
        }

    def update_profile_from_report(
        self, profile: StudentProfile, report: dict[str, Any]
    ) -> dict[str, Any]:
        """根据评估报告更新学生画像。"""
        updated = profile.model_dump() if hasattr(profile, "model_dump") else {}
        if not updated:
            updated = {}

        updated.update({
            "last_evaluated": True,
            "evaluation_score": report["score"],
            "evaluation_level": report["level"],
            "evaluation_analysis": report.get("analysis", {}),
            "knowledge_mastery": report.get("analysis", {}).get("knowledge_mastery_score", 0),
        })

        return updated


_evaluation_service: EvaluationService | None = None


def get_evaluation_service() -> EvaluationService:
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = EvaluationService()
    return _evaluation_service