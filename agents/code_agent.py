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
    """星火未配置时的规则兜底代码案例生成。"""
    level = profile.knowledge_level if profile else "beginner"
    weakness = profile.weakness if profile else ""

    examples = []
    if "循环" in topic or "loop" in topic.lower():
        examples = _generate_loop_examples(level)
    elif "函数" in topic or "function" in topic.lower():
        examples = _generate_function_examples(level)
    elif "面向对象" in topic or "oop" in topic.lower():
        examples = _generate_oop_examples(level)
    else:
        examples = _generate_generic_examples(topic, level)

    return CodeSet(
        topic=topic,
        total_count=len(examples),
        examples=examples,
        suggestions=_generate_suggestions(level, weakness),
        source="heuristic"
    )


def _generate_loop_examples(level: str) -> list[CodeExample]:
    return [
        CodeExample(
            title="for循环打印数字",
            description="使用for循环和range函数打印1到5的数字",
            code="for i in range(1, 6):\n    print(f\"数字: {i}\")",
            language="python",
            output="数字: 1\n数字: 2\n数字: 3\n数字: 4\n数字: 5",
            key_points=["for循环", "range函数", "格式化输出"],
            difficulty="easy"
        ),
        CodeExample(
            title="while循环累加",
            description="使用while循环计算1到100的累加和",
            code="sum_result = 0\ni = 1\nwhile i <= 100:\n    sum_result += i\n    i += 1\nprint(f\"1+2+...+100 = {sum_result}\")",
            language="python",
            output="1+2+...+100 = 5050",
            key_points=["while循环", "累加器", "循环终止条件"],
            difficulty="easy"
        ),
        CodeExample(
            title="嵌套循环打印图案",
            description="使用嵌套循环打印直角三角形",
            code="for i in range(1, 6):\n    for j in range(i):\n        print(\"*\", end=\"\")\n    print()",
            language="python",
            output="*\n**\n***\n****\n*****",
            key_points=["嵌套循环", "print参数", "循环控制"],
            difficulty="medium"
        ),
        CodeExample(
            title="break与continue",
            description="演示break退出循环和continue跳过本次迭代",
            code="for i in range(1, 11):\n    if i == 3:\n        continue\n    if i == 8:\n        break\n    print(i, end=\" \")",
            language="python",
            output="1 2 4 5 6 7",
            key_points=["break语句", "continue语句", "循环控制"],
            difficulty="medium"
        ),
        CodeExample(
            title="斐波那契数列",
            description="使用循环生成斐波那契数列的前n项",
            code="def fibonacci(n):\n    fib = [0, 1]\n    for i in range(2, n):\n        fib.append(fib[i-1] + fib[i-2])\n    return fib[:n]\n\nprint(fibonacci(10))",
            language="python",
            output="[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]",
            key_points=["循环应用", "列表操作", "算法实现"],
            difficulty="hard"
        ),
    ]


def _generate_function_examples(level: str) -> list[CodeExample]:
    return [
        CodeExample(
            title="简单函数定义",
            description="定义并调用一个简单的问候函数",
            code="def greet(name):\n    return f\"Hello, {name}!\"\n\nmessage = greet(\"Alice\")\nprint(message)",
            language="python",
            output="Hello, Alice!",
            key_points=["函数定义", "参数传递", "返回值"],
            difficulty="easy"
        ),
        CodeExample(
            title="默认参数函数",
            description="使用默认参数简化函数调用",
            code="def power(base, exponent=2):\n    return base ** exponent\n\nprint(power(3))\nprint(power(3, 3))",
            language="python",
            output="9\n27",
            key_points=["默认参数", "幂运算", "函数调用"],
            difficulty="easy"
        ),
        CodeExample(
            title="递归函数-阶乘",
            description="使用递归计算阶乘",
            code="def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)\n\nprint(f\"5! = {factorial(5)}\")\nprint(f\"10! = {factorial(10)}\")",
            language="python",
            output="5! = 120\n10! = 3628800",
            key_points=["递归函数", "基线条件", "函数调用栈"],
            difficulty="medium"
        ),
        CodeExample(
            title="lambda表达式",
            description="使用lambda创建匿名函数",
            code="square = lambda x: x ** 2\nnumbers = [1, 2, 3, 4, 5]\nsquared = list(map(square, numbers))\nprint(squared)",
            language="python",
            output="[1, 4, 9, 16, 25]",
            key_points=["lambda", "map函数", "匿名函数"],
            difficulty="medium"
        ),
        CodeExample(
            title="装饰器基础",
            description="创建和使用简单的装饰器",
            code="def timer(func):\n    def wrapper(*args, **kwargs):\n        import time\n        start = time.time()\n        result = func(*args, **kwargs)\n        print(f\"执行时间: {time.time() - start:.4f}秒\")\n        return result\n    return wrapper\n\n@timer\ndef slow_sum(n):\n    return sum(range(n))\n\nslow_sum(1000000)",
            language="python",
            output="执行时间: 0.0321秒\n500000500000",
            key_points=["装饰器", "闭包", "函数封装"],
            difficulty="hard"
        ),
    ]


def _generate_oop_examples(level: str) -> list[CodeExample]:
    return [
        CodeExample(
            title="类和对象创建",
            description="定义一个简单的学生类并创建对象",
            code="class Student:\n    def __init__(self, name, age):\n        self.name = name\n        self.age = age\n    \n    def introduce(self):\n        return f\"我是{self.name}，今年{self.age}岁\"\n\ns = Student(\"小明\", 20)\nprint(s.introduce())",
            language="python",
            output="我是小明，今年20岁",
            key_points=["类定义", "__init__", "实例方法"],
            difficulty="easy"
        ),
        CodeExample(
            title="类的继承",
            description="演示类的继承和方法重写",
            code="class Animal:\n    def __init__(self, name):\n        self.name = name\n    \n    def speak(self):\n        return \"动物叫声\"\n\nclass Dog(Animal):\n    def speak(self):\n        return f\"{self.name}说: 汪汪！\"\n\ndog = Dog(\"旺财\")\nprint(dog.speak())",
            language="python",
            output="旺财说: 汪汪！",
            key_points=["类的继承", "方法重写", "多态"],
            difficulty="medium"
        ),
        CodeExample(
            title="属性封装",
            description="使用property装饰器实现属性封装",
            code="class BankAccount:\n    def __init__(self, balance):\n        self.__balance = balance\n    \n    @property\n    def balance(self):\n        return self.__balance\n    \n    @balance.setter\n    def balance(self, value):\n        if value >= 0:\n            self.__balance = value\n\nacc = BankAccount(1000)\nprint(f\"余额: {acc.balance}\")\nacc.balance = 2000\nprint(f\"新余额: {acc.balance}\")",
            language="python",
            output="余额: 1000\n新余额: 2000",
            key_points=["属性封装", "property装饰器", "私有属性"],
            difficulty="hard"
        ),
    ]


def _generate_generic_examples(topic: str, level: str) -> list[CodeExample]:
    return [
        CodeExample(
            title=f"{topic}基础示例",
            description=f"演示{topic}的基本用法",
            code=f"# {topic}基础示例\n# 请根据学习内容理解以下代码",
            language="python",
            output="",
            key_points=[topic, "基础语法"],
            difficulty="easy"
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
            return lp.path_name
        return state.get("user_input", "Python基础")

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