from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from backend.integrations.spark.client import get_spark_client
from schemas.profile import StudentProfile

logger = logging.getLogger(__name__)


def _prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts" / "evaluation_agent.md"


def load_evaluation_prompt() -> str:
    path = _prompt_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "你是学习评估助手，根据学生学习行为和资源使用情况评估学习效果。"


def calculate_study_score(profile: StudentProfile, resource_usage: dict[str, Any]) -> int:
    """根据资源使用情况计算学习评分(0-100)。"""
    score = 70

    quiz_result = resource_usage.get("quiz_set", {})
    if quiz_result:
        questions = quiz_result.get("questions", [])
        if questions:
            score += 10

    code_result = resource_usage.get("code_set", {})
    if code_result:
        examples = code_result.get("examples", [])
        if examples:
            score += 10

    video_result = resource_usage.get("video_script", {})
    if video_result:
        scenes = video_result.get("scenes", [])
        if scenes:
            score += 5

    if profile.knowledge_level == "beginner":
        score = min(score + 5, 100)

    return score


def generate_evaluation_report(profile: StudentProfile, resource_usage: dict[str, Any]) -> dict[str, Any]:
    """生成评估报告。"""
    score = calculate_study_score(profile, resource_usage)

    if score >= 90:
        level = "优秀"
        comment = "学习表现非常出色！继续保持！"
    elif score >= 75:
        level = "良好"
        comment = "学习效果不错，可以继续深入！"
    elif score >= 60:
        level = "中等"
        comment = "基本掌握了内容，建议多做练习。"
    else:
        level = "需加强"
        comment = "需要更多练习来巩固知识。"

    strengths: list[str] = []
    weaknesses: list[str] = []

    if profile.weakness:
        weaknesses.append(f"薄弱点: {profile.weakness}")

    if resource_usage.get("quiz_set"):
        weaknesses.append("需要通过练习巩固知识点")

    if resource_usage.get("code_set"):
        strengths.append("代码示例有助于实践理解")

    if resource_usage.get("mindmap"):
        strengths.append("思维导图帮助建立知识体系")

    suggestions: list[str] = [
        "建议每天坚持学习，保持节奏",
        "多做练习题巩固知识点",
        "可以尝试自己编写代码",
    ]

    if weaknesses:
        suggestions.insert(0, f"重点加强: {', '.join(weaknesses)}")

    return {
        "score": score,
        "level": level,
        "comment": comment,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggestions": suggestions,
        "evaluated": True,
        "source": "heuristic"
    }


class EvaluationAgent(BaseAgent):
    """学习评估Agent：根据学习行为和资源使用评估学习效果。"""

    name = "evaluation"

    def __init__(self) -> None:
        self.spark = get_spark_client()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        profile_data = state.get("student_profile", {})
        profile = StudentProfile(**profile_data) if profile_data else StudentProfile()

        resource_usage = {
            "ppt_deck": state.get("ppt_deck", {}),
            "quiz_set": state.get("quiz_set", {}),
            "code_set": state.get("code_set", {}),
            "mindmap": state.get("mindmap", {}),
            "video_script": state.get("video_script", {}),
        }

        report = await self._generate_evaluation(profile, resource_usage)

        updated_profile = profile_data.copy() if profile_data else {}
        updated_profile.update({
            "last_evaluated": True,
            "evaluation_score": report["score"],
            "evaluation_level": report["level"],
        })

        return {
            "student_profile": updated_profile,
            "evaluation_report": report,
            "messages": [
                {"role": "assistant", "content": self._format_report_markdown(report)}
            ],
        }

    def _format_report_markdown(self, report: dict[str, Any]) -> str:
        lines = [
            "## 📊 学习评估报告\n",
            f"**综合评分**: {report['score']}/100 ({report['level']})\n",
            f"**评价**: {report['comment']}\n",
        ]

        if report.get("strengths"):
            lines.append("\n### ✅ 优势\n")
            for s in report["strengths"]:
                lines.append(f"- {s}")

        if report.get("weaknesses"):
            lines.append("\n### ⚠️ 待加强\n")
            for w in report["weaknesses"]:
                lines.append(f"- {w}")

        if report.get("suggestions"):
            lines.append("\n### 💡 建议\n")
            for s in report["suggestions"]:
                lines.append(f"- {s}")

        return "\n".join(lines)

    async def _generate_evaluation(self, profile: StudentProfile, resource_usage: dict[str, Any]) -> dict[str, Any]:
        if self.spark.configured:
            try:
                return await self._generate_with_spark(profile, resource_usage)
            except Exception as exc:
                logger.warning("星火评估失败，使用规则引擎: %s", exc)

        return generate_evaluation_report(profile, resource_usage)

    async def _generate_with_spark(self, profile: StudentProfile, resource_usage: dict[str, Any]) -> dict[str, Any]:
        system_prompt = load_evaluation_prompt()

        usage_summary = []
        for key, value in resource_usage.items():
            if value:
                usage_summary.append(f"- {key}: 已使用")
            else:
                usage_summary.append(f"- {key}: 未使用")

        user_prompt = (
            f"请根据以下信息评估学生学习效果：\n\n"
            f"学生画像: {profile.model_dump_json()}\n\n"
            f"资源使用情况:\n" + "\n".join(usage_summary) + "\n\n"
            f"输出JSON格式：score(0-100), level(优秀/良好/中等/需加强), comment, "
            f"strengths(list), weaknesses(list), suggestions(list), evaluated(true)"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        data = await self.spark.chat_json(messages)
        data["source"] = "spark"
        return data