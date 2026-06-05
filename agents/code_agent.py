from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from backend.integrations.spark.client import get_spark_client
from schemas.profile import CodeExample, CodeSet, LearningPath, StudentProfile

logger = logging.getLogger(__name__)


def _prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts" / "code_agent.md"


def load_code_prompt() -> str:
    path = _prompt_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "你是代码案例生成助手，根据学习主题生成代码示例。"


def heuristic_code(topic: str, profile: StudentProfile | None = None) -> CodeSet:
    """星火未配置时的规则兜底代码案例生成。通用模板，适用于任意学科。"""
    level = profile.knowledge_level if profile else "beginner"
    weakness = profile.weakness if profile else ""

    examples = _generate_generic_examples(topic, level)

    return CodeSet(
        topic=topic,
        total_count=len(examples),
        examples=examples,
        suggestions=_generate_suggestions(level, weakness),
        source="heuristic",
    )


def _generate_generic_examples(topic: str, level: str) -> list[CodeExample]:
    """通用代码示例生成，适用于任意学科，按水平分级。"""
    if level == "advanced":
        return [
            CodeExample(
                title=f"{topic}高级应用",
                description=f"演示{topic}在实际项目中的高级应用",
                code=f"# {topic}高级应用示例\n# 请在LLM模式下查看详细实现",
                language="python",
                output="（LLM模式下提供完整代码和运行结果）",
                key_points=[topic, "高级应用", "性能优化"],
                difficulty="hard",
            ),
            CodeExample(
                title=f"{topic}设计模式",
                description=f"在{topic}中应用常见的设计模式",
                code=f"# {topic}设计模式应用\n# 请在LLM模式下查看详细实现",
                language="python",
                output="（LLM模式下提供完整代码和运行结果）",
                key_points=[topic, "设计模式", "架构设计"],
                difficulty="hard",
            ),
        ]
    elif level == "intermediate":
        return [
            CodeExample(
                title=f"{topic}进阶用法",
                description=f"演示{topic}的进阶使用方式",
                code=f"# {topic}进阶用法\n# 请在LLM模式下查看详细实现",
                language="python",
                output="（LLM模式下提供完整代码和运行结果）",
                key_points=[topic, "进阶技巧", "常见误区"],
                difficulty="medium",
            ),
            CodeExample(
                title=f"{topic}实践案例",
                description=f"{topic}在实际场景中的应用案例",
                code=f"# {topic}实践案例\n# 请在LLM模式下查看详细实现",
                language="python",
                output="（LLM模式下提供完整代码和运行结果）",
                key_points=[topic, "实践应用", "问题解决"],
                difficulty="medium",
            ),
        ]
    else:
        return [
            CodeExample(
                title=f"{topic}基础入门",
                description=f"了解{topic}的基本概念和用法",
                code=f"# {topic}基础入门\n# 请在LLM模式下查看详细代码",
                language="python",
                output="（LLM模式下提供完整代码和运行结果）",
                key_points=[topic, "基本概念", "入门用法"],
                difficulty="easy",
            ),
            CodeExample(
                title=f"{topic}简单示例",
                description=f"通过简单示例理解{topic}的核心用法",
                code=f"# {topic}简单示例\n# 请在LLM模式下查看详细代码",
                language="python",
                output="（LLM模式下提供完整代码和运行结果）",
                key_points=[topic, "核心用法", "基础练习"],
                difficulty="easy",
            ),
        ]


def _generate_suggestions(level: str, weakness: str) -> list[str]:
    suggestions = [
        "先理解代码逻辑，再动手敲一遍",
        "尝试修改代码参数，观察输出变化",
        "自己编写类似功能的代码",
    ]
    if weakness:
        suggestions.insert(0, f"针对薄弱点：{weakness}，多做相关练习")
    if level == "beginner":
        suggestions.append("建议从简单例子开始，逐步深入")
    return suggestions


class CodeAgent(BaseAgent):
    """代码案例Agent：根据学习主题生成代码示例。"""

    name = "code"

    def __init__(self) -> None:
        self.spark = get_spark_client()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        topic = self._extract_topic(state)
        profile_data = state.get("student_profile", {})
        profile = StudentProfile(**profile_data) if profile_data else None

        code_set, source = await self._generate_code(topic, profile)

        return {
            "code_set": code_set.model_dump(),
            "messages": [
                {"role": "assistant", "content": f"【代码案例】{code_set.topic} | 共{code_set.total_count}个示例（来源: {source}）"},
                {"role": "assistant", "content": code_set.to_markdown()}
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

    async def _generate_code(self, topic: str, profile: StudentProfile | None) -> tuple[CodeSet, str]:
        if self.spark.configured:
            try:
                return await self._generate_with_spark(topic, profile), "spark"
            except Exception as exc:
                logger.warning("星火代码生成失败，使用规则兜底: %s", exc)

        return heuristic_code(topic, profile), "heuristic"

    async def _generate_with_spark(self, topic: str, profile: StudentProfile | None) -> CodeSet:
        system_prompt = load_code_prompt()
        level = profile.knowledge_level if profile else "beginner"

        user_prompt = (
            f"请为主题「{topic}」生成代码案例，"
            f"难度：{level}，"
            f"输出JSON格式：topic, total_count, examples(含title,description,code,language,output,key_points,difficulty), suggestions"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        data = await self.spark.chat_json(messages)
        data["source"] = "spark"
        return CodeSet.model_validate(data)