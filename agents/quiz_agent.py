from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from backend.integrations.spark.client import get_spark_client
from schemas.profile import LearningPath, QuizQuestion, QuizSet, StudentProfile

logger = logging.getLogger(__name__)


def _prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts" / "quiz_agent.md"


def load_quiz_prompt() -> str:
    path = _prompt_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "你是题库生成助手，根据学习主题生成练习题。"


def heuristic_quiz(topic: str, profile: StudentProfile | None = None) -> QuizSet:
    """星火未配置时的规则兜底题库生成。通用模板，围绕任意学科主题。"""
    level = profile.knowledge_level if profile else "beginner"
    weakness = profile.weakness if profile else ""

    questions = _generate_generic_questions(topic, level)

    return QuizSet(
        topic=topic,
        total_count=len(questions),
        questions=questions,
        suggestions=_generate_suggestions(level, weakness),
        source="heuristic",
    )


def _generate_generic_questions(topic: str, level: str) -> list[QuizQuestion]:
    """通用题目生成，适用于任意学科主题，按水平调整难度。"""
    difficulty = "easy" if level == "beginner" else ("medium" if level == "intermediate" else "hard")

    return [
        QuizQuestion(
            question_type="choice",
            difficulty="easy",
            question=f"关于「{topic}」的核心概念，以下哪项描述最准确？",
            options=[
                f"「{topic}」是该领域的基础理论和实践方法",
                f"「{topic}」只是一种辅助工具",
                f"「{topic}」已被淘汰不再使用",
                "以上说法都不正确",
            ],
            answer=f"「{topic}」是该领域的基础理论和实践方法",
            explanation="理解核心概念的定义和意义是学习的第一步",
            knowledge_point=f"{topic}基本概念",
        ),
        QuizQuestion(
            question_type="true_false",
            difficulty="easy",
            question=f"学习「{topic}」时，应该先掌握基础概念再进入实践应用。",
            answer="True",
            explanation="循序渐进的学习方法能帮助建立扎实的知识基础",
            knowledge_point=f"{topic}学习方法",
        ),
        QuizQuestion(
            question_type="choice",
            difficulty=difficulty,
            question=f"以下哪项是深入学习「{topic}」的最佳方式？",
            options=[
                "只阅读教材不做练习",
                "结合理论学习和实践操作",
                "跳过基础直接学习高级内容",
                "只看不做",
            ],
            answer="结合理论学习和实践操作",
            explanation="理论与实践结合是掌握知识的最有效方式",
            knowledge_point=f"{topic}学习策略",
        ),
        QuizQuestion(
            question_type="blank",
            difficulty=difficulty,
            question=f"「{topic}」的学习通常包括：概念理解、______、实践应用三个阶段。",
            answer="方法掌握",
            explanation="学习过程应包含理解、掌握方法、实践三个环节",
            knowledge_point=f"{topic}学习流程",
        ),
        QuizQuestion(
            question_type="true_false",
            difficulty=difficulty,
            question=f"在学习「{topic}」遇到困难时，应该回到基础概念重新理解。",
            answer="True",
            explanation="大部分学习困难都源于基础概念不够扎实",
            knowledge_point=f"{topic}问题解决",
        ),
    ]


def _generate_suggestions(level: str, weakness: str) -> list[str]:
    suggestions = [
        "先理解概念，再动手实践",
        "多做练习题巩固知识点",
        "不懂的地方及时复习",
    ]
    if weakness:
        suggestions.insert(0, f"重点关注薄弱环节：{weakness}")
    if level == "beginner":
        suggestions.append("建议从简单题目开始，循序渐进")
    return suggestions


class QuizAgent(BaseAgent):
    """题库生成Agent：根据学习主题生成练习题。"""

    name = "quiz"

    def __init__(self) -> None:
        self.spark = get_spark_client()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        topic = self._extract_topic(state)
        profile_data = state.get("student_profile", {})
        profile = StudentProfile(**profile_data) if profile_data else None

        quiz_set, source = await self._generate_quiz(topic, profile)

        return {
            "quiz_set": quiz_set.model_dump(),
            "messages": [
                {"role": "assistant", "content": f"【练习题库】{quiz_set.topic} | 共{quiz_set.total_count}道题（来源: {source}）"},
                {"role": "assistant", "content": quiz_set.to_markdown()}
            ],
        }

    def _extract_topic(self, state: dict[str, Any]) -> str:
        if state.get("learning_path"):
            lp = LearningPath(**state["learning_path"])
            if lp.path_name and lp.path_name != "unknown":
                return lp.path_name
        profile_data = state.get("student_profile", {})
        if profile_data:
            p = StudentProfile(**profile_data)
            if p.learning_goal_text and p.learning_goal_text not in ("unknown", ""):
                return p.learning_goal_text[:30]
            if p.major and p.major not in ("", "unknown"):
                return p.major
        user_input = state.get("user_input", "")
        return user_input[:30] if user_input else "通用学习"

    async def _generate_quiz(self, topic: str, profile: StudentProfile | None) -> tuple[QuizSet, str]:
        if self.spark.configured:
            try:
                return await self._generate_with_spark(topic, profile), "spark"
            except Exception as exc:
                logger.warning("星火题库生成失败，使用规则兜底: %s", exc)

        return heuristic_quiz(topic, profile), "heuristic"

    async def _generate_with_spark(self, topic: str, profile: StudentProfile | None) -> QuizSet:
        system_prompt = load_quiz_prompt()
        level = profile.knowledge_level if profile else "beginner"
        weakness = profile.weakness if profile else ""

        user_prompt = (
            f"请为主题「{topic}」生成练习题，"
            f"难度：{level}，薄弱点：{weakness}，"
            f"包含选择/判断/填空/编程题型，"
            f"输出JSON格式：topic, total_count, questions(含所有字段), suggestions"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        data = await self.spark.chat_json(messages)
        data["source"] = "spark"
        return QuizSet.model_validate(data)