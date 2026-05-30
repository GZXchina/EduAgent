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
    """星火未配置时的规则兜底题库生成。"""
    level = profile.knowledge_level if profile else "beginner"
    weakness = profile.weakness if profile else ""

    questions = []
    if "循环" in topic or "loop" in topic.lower():
        questions = _generate_loop_questions(level, weakness)
    elif "函数" in topic or "function" in topic.lower():
        questions = _generate_function_questions(level, weakness)
    elif "面向对象" in topic or "oop" in topic.lower():
        questions = _generate_oop_questions(level, weakness)
    else:
        questions = _generate_generic_questions(topic, level)

    return QuizSet(
        topic=topic,
        total_count=len(questions),
        questions=questions,
        suggestions=_generate_suggestions(level, weakness),
        source="heuristic"
    )


def _generate_loop_questions(level: str, weakness: str) -> list[QuizQuestion]:
    base_difficulty = "easy" if level == "beginner" else "medium"
    return [
        QuizQuestion(
            question_type="choice",
            difficulty="easy",
            question="以下哪个是Python中for循环的正确语法？",
            options=["for i in range(5):", "for i = 0; i < 5; i++", "for (i = 0; i < 5; i++)", "foreach i in range(5)"],
            answer="for i in range(5):",
            explanation="Python使用for...in语法遍历序列",
            knowledge_point="for循环基础"
        ),
        QuizQuestion(
            question_type="true_false",
            difficulty="easy",
            question="while循环必须有循环条件，否则会变成死循环。",
            answer="True",
            explanation="while循环依靠条件判断来控制循环执行，需要确保条件最终会变为False",
            knowledge_point="while循环基础"
        ),
        QuizQuestion(
            question_type="blank",
            difficulty="medium",
            question="请补全代码：for i in ___（5）：print(i)",
            answer="range",
            explanation="range()函数生成数字序列",
            knowledge_point="range函数"
        ),
        QuizQuestion(
            question_type="programming",
            difficulty="medium",
            question="请用for循环打印1到10的所有偶数。",
            answer="for i in range(2, 11, 2):\n    print(i)",
            explanation="使用range的步长参数2来生成偶数序列",
            knowledge_point="for循环应用"
        ),
        QuizQuestion(
            question_type="choice",
            difficulty="hard",
            question="以下代码的输出是什么？\nfor i in range(3):\n    for j in range(2):\n        print(i, j)",
            options=["3行输出", "6行输出", "5行输出", "9行输出"],
            answer="6行输出",
            explanation="外层循环3次，内层循环2次，总共3*2=6次输出",
            knowledge_point="循环嵌套"
        ),
    ]


def _generate_function_questions(level: str, weakness: str) -> list[QuizQuestion]:
    return [
        QuizQuestion(
            question_type="choice",
            difficulty="easy",
            question="Python中定义函数的关键字是？",
            options=["function", "def", "func", "define"],
            answer="def",
            explanation="Python使用def关键字来定义函数",
            knowledge_point="函数基础"
        ),
        QuizQuestion(
            question_type="blank",
            difficulty="medium",
            question="请补全代码使函数返回两个数的和：def add(a, b): ___ a + b",
            answer="return",
            explanation="return语句用于返回函数结果",
            knowledge_point="函数返回值"
        ),
        QuizQuestion(
            question_type="programming",
            difficulty="medium",
            question="编写一个函数，判断一个数是否为素数。",
            answer="def is_prime(n):\n    if n < 2:\n        return False\n    for i in range(2, int(n**0.5)+1):\n        if n % i == 0:\n            return False\n    return True",
            explanation="素数定义为大于1且只能被1和自身整除的数",
            knowledge_point="函数应用"
        ),
    ]


def _generate_oop_questions(level: str, weakness: str) -> list[QuizQuestion]:
    return [
        QuizQuestion(
            question_type="choice",
            difficulty="easy",
            question="Python中定义类的关键字是？",
            options=["class", "def", "object", "type"],
            answer="class",
            explanation="Python使用class关键字定义类",
            knowledge_point="类基础"
        ),
        QuizQuestion(
            question_type="choice",
            difficulty="medium",
            question="类的__init__方法用于？",
            options=["析构对象", "初始化对象", "定义属性", "继承类"],
            answer="初始化对象",
            explanation="__init__在创建类的实例时自动调用，用于初始化属性",
            knowledge_point="类的构造方法"
        ),
    ]


def _generate_generic_questions(topic: str, level: str) -> list[QuizQuestion]:
    return [
        QuizQuestion(
            question_type="choice",
            difficulty="easy",
            question=f"关于{topic}，以下说法正确的是？",
            options=[f"{topic}是重要概念", f"{topic}很难", f"{topic}不需要学习", f"以上都不对"],
            answer=f"{topic}是重要概念",
            explanation="本题目考察对基本概念的理解",
            knowledge_point=f"{topic}基础"
        ),
        QuizQuestion(
            question_type="true_false",
            difficulty="easy",
            question=f"{topic}是Python学习的重点内容。",
            answer="True",
            explanation="理解核心概念对学习很重要",
            knowledge_point=f"{topic}概念"
        ),
        QuizQuestion(
            question_type="programming",
            difficulty="medium",
            question=f"请编写一个{topic}相关的代码示例。",
            answer=f"# {topic}示例\n# 请根据学习内容编写代码",
            explanation="实践是最好的学习方式",
            knowledge_point=f"{topic}应用"
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
            return lp.path_name
        return state.get("user_input", "Python基础")

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