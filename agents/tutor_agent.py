from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from backend.integrations.spark.client import get_spark_client
from rag.retriever import KnowledgeRetriever
from schemas.profile import StudentProfile

logger = logging.getLogger(__name__)

SAFE_ANSWERS = {
    "hello": "你好！有什么Python问题我可以帮你解答吗？",
    "hi": "嗨！欢迎提问，我会尽力帮助你学习Python。",
    "thank": "不客气！继续加油学习Python吧！",
    "bye": "再见！祝学习愉快！",
}

BLOCKED_KEYWORDS = ["暴力", "赌博", "色情", "政治", "黑客", "病毒"]


def _prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts" / "tutor_agent.md"


def load_tutor_prompt() -> str:
    path = _prompt_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "你是答疑辅导助手，结合RAG知识库检索结果回答学生问题。"


def is_safe_question(question: str) -> bool:
    """检查问题是否安全。"""
    q_lower = question.lower()
    for keyword in BLOCKED_KEYWORDS:
        if keyword in q_lower:
            return False
    return True


def heuristic_answer(question: str) -> str:
    """星火未配置时的规则兜底答疑。"""
    q_lower = question.lower()

    for keyword, answer in SAFE_ANSWERS.items():
        if keyword in q_lower:
            return answer

    if "循环" in question or "for" in q_lower or "while" in q_lower:
        return (
            "关于循环的问题：\n"
            "- for循环：适合已知迭代次数的场景，使用`for i in range(n):`\n"
            "- while循环：适合条件驱动场景，注意设置退出条件避免死循环\n"
            "- break可以提前退出循环，continue跳过本次迭代\n"
            "如果你有具体的循环问题，请详细描述，我来帮你分析。"
        )

    if "函数" in question or "def" in q_lower:
        return (
            "关于函数的问题：\n"
            "- 定义函数使用`def 函数名(参数):`\n"
            "- 函数可以返回值，使用`return`语句\n"
            "- 参数可以有默认值，变成可选参数\n"
            "如果你有具体的函数问题，请详细描述，我来帮你分析。"
        )

    if "类" in question or "class" in q_lower or "对象" in question:
        return (
            "关于面向对象的问题：\n"
            "- 类是抽象的数据类型模板，使用`class`关键字定义\n"
            "- 对象是类的实例，通过`类名()`创建\n"
            "- `__init__`是构造方法，用于初始化对象属性\n"
            "如果你有具体的OOP问题，请详细描述，我来帮你分析。"
        )

    return (
        "这是一个好问题！\n"
        "根据你学习的内容，我可以帮你：\n"
        "1. 解释概念和语法\n"
        "2. 分析代码逻辑\n"
        "3. 找出错误原因\n"
        "4. 提供学习建议\n\n"
        "请更具体地描述你的问题，我好针对性地帮助你。"
    )


class TutorAgent(BaseAgent):
    """答疑辅导Agent：结合RAG知识库和星火大模型回答学生问题。"""

    name = "tutor"

    def __init__(self) -> None:
        self.spark = get_spark_client()
        self.retriever = KnowledgeRetriever()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        question = self._extract_question(state)
        profile_data = state.get("student_profile", {})
        profile = StudentProfile(**profile_data) if profile_data else None

        if not question.strip():
            return {"messages": [{"role": "assistant", "content": "我没有收到你的问题，请重新输入。"}]}

        if not is_safe_question(question):
            return {"messages": [{"role": "assistant", "content": "抱歉，我无法回答涉及敏感内容的问题。请换个话题。"}]}

        answer = await self._generate_answer(question, profile)

        return {
            "messages": [{"role": "assistant", "content": answer}],
        }

    def _extract_question(self, state: dict[str, Any]) -> str:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return state.get("user_input", "")

    async def _generate_answer(self, question: str, profile: StudentProfile | None) -> str:
        if self.spark.configured:
            try:
                docs = await self.retriever.query(question, k=3)
                return await self._generate_with_spark(question, docs, profile)
            except Exception as exc:
                logger.warning("星火答疑失败，使用规则兜底: %s", exc)

        return heuristic_answer(question)

    async def _generate_with_spark(self, question: str, docs: list[dict[str, Any]], profile: StudentProfile | None) -> str:
        system_prompt = load_tutor_prompt()
        level = profile.knowledge_level if profile else "intermediate"

        context = ""
        if docs:
            context = "【相关知识】\n" + "\n".join([f"- {d.get('content', '')[:300]}" for d in docs[:2]]) + "\n\n"

        user_prompt = (
            f"{context}"
            f"【用户问题】{question}\n\n"
            f"用户知识水平：{level}\n"
            f"请结合相关知识回答用户问题，回答要简洁、有条理、适合学习者理解。"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        return await self.spark.chat(messages)