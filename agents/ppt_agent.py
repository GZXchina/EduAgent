from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from backend.integrations.spark.client import get_spark_client
from schemas.profile import LearningPath, PPTSlide, PPTDeck, StudentProfile

logger = logging.getLogger(__name__)


def _prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts" / "ppt_agent.md"


def load_ppt_prompt() -> str:
    path = _prompt_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "你是PPT生成助手，根据学习主题生成Markdown课件结构。"


def heuristic_ppt(topic: str, profile: StudentProfile | None = None) -> PPTDeck:
    """星火未配置时的规则兜底PPT生成。"""
    level = profile.knowledge_level if profile else "beginner"
    style = profile.learning_style if profile else "reading"

    slide_count = 8 if level == "beginner" else 6

    slides = []
    if "循环" in topic or "loop" in topic.lower():
        slides = _generate_loop_ppt(style)
    elif "函数" in topic or "function" in topic.lower():
        slides = _generate_function_ppt(style)
    elif "面向对象" in topic or "oop" in topic.lower():
        slides = _generate_oop_ppt(style)
    else:
        slides = _generate_generic_ppt(topic, style, slide_count)

    return PPTDeck(
        topic=topic,
        total_slides=len(slides),
        slides=slides,
        source="heuristic"
    )


def _generate_loop_ppt(style: str) -> list[PPTSlide]:
    resources = ["图解教程", "动画演示"] if style == "visual" else ["文档教程", "代码练习"]
    return [
        PPTSlide(slide_number=1, title="循环结构概述", content=["循环的概念与作用", "循环的应用场景", "循环的优点"], notes="先讲清为什么需要循环"),
        PPTSlide(slide_number=2, title="for循环", content=["for循环语法", "range函数的使用", "遍历列表"], notes="配合代码演示"),
        PPTSlide(slide_number=3, title="while循环", content=["while循环语法", "条件控制", "无限循环的避免"], notes="强调条件判断"),
        PPTSlide(slide_number=4, title="循环嵌套", content=["嵌套循环的概念", "九九乘法表", "打印图案"], notes="逐步演示"),
        PPTSlide(slide_number=5, title="break与continue", content=["break退出循环", "continue跳过本次", "区别与使用场景"], notes="对比讲解"),
        PPTSlide(slide_number=6, title="循环经典案例", content=["斐波那契数列", "质数判断", "算法优化"], notes="综合应用"),
        PPTSlide(slide_number=7, title="常见错误与调试", content=["索引越界", "死循环", "缩进错误"], notes="实操演示"),
        PPTSlide(slide_number=8, title="练习与小结", content=["上机练习", "知识点回顾", "作业布置"], notes="巩固练习"),
    ]


def _generate_function_ppt(style: str) -> list[PPTSlide]:
    return [
        PPTSlide(slide_number=1, title="函数基础", content=["函数的概念", "函数的定义与调用", "函数的好处"], notes="从概念入手"),
        PPTSlide(slide_number=2, title="函数参数", content=["位置参数", "关键字参数", "默认参数"], notes="区分参数类型"),
        PPTSlide(slide_number=3, title="返回值", content=["return语句", "返回多个值", "返回None的情况"], notes="实际案例"),
        PPTSlide(slide_number=4, title="变量作用域", content=["局部变量", "全局变量", "global关键字"], notes="重点讲解"),
        PPTSlide(slide_number=5, title="匿名函数", content=["lambda表达式", "map/filter配合", "lambda适用场景"], notes="简化代码"),
        PPTSlide(slide_number=6, title="递归函数", content=["递归的概念", "递归调用过程", "递归终止条件"], notes="画图演示"),
        PPTSlide(slide_number=7, title="函数模块", content=["模块导入", "标准库", "自定义模块"], notes="实战应用"),
        PPTSlide(slide_number=8, title="练习与总结", content=["编写函数", "调试技巧", "本章小结"], notes="综合练习"),
    ]


def _generate_oop_ppt(style: str) -> list[PPTSlide]:
    return [
        PPTSlide(slide_number=1, title="面向对象概述", content=["OOP概念", "类与对象", "面向过程vs面向对象"], notes="对比讲解"),
        PPTSlide(slide_number=2, title="类的定义", content=["class关键字", "__init__方法", "self参数"], notes="代码演示"),
        PPTSlide(slide_number=3, title="属性与方法", content=["实例属性", "类属性", "实例方法"], notes="区分概念"),
        PPTSlide(slide_number=4, title="继承", content=["单继承", "多继承", "super()函数"], notes="重点内容"),
        PPTSlide(slide_number=5, title="多态与封装", content=["多态概念", "封装原则", "私有属性"], notes="实际应用"),
        PPTSlide(slide_number=6, title="特殊方法", content=["__str__", "__len__", "运算符重载"], notes="拓展内容"),
        PPTSlide(slide_number=7, title="设计模式入门", content=["单例模式", "工厂模式", "实际应用"], notes="进阶内容"),
        PPTSlide(slide_number=8, title="项目实战", content=["需求分析", "类设计", "代码实现"], notes="综合项目"),
    ]


def _generate_generic_ppt(topic: str, style: str, count: int) -> list[PPTSlide]:
    slides = []
    for i in range(1, count + 1):
        if i == 1:
            title = f"{topic}概述"
            content = ["概念介绍", "学习目标", "知识框架"]
        elif i == count:
            title = "总结与练习"
            content = ["知识点回顾", "练习题", "拓展学习"]
        else:
            title = f"{topic}第{i}部分"
            content = [f"核心内容{i-1}", "代码示例", "练习实践"]

        slides.append(PPTSlide(slide_number=i, title=title, content=content))
    return slides


class PPTAgent(BaseAgent):
    """PPT生成Agent：根据学习主题生成Markdown课件。"""

    name = "ppt"

    def __init__(self) -> None:
        self.spark = get_spark_client()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        topic = self._extract_topic(state)
        profile_data = state.get("student_profile", {})
        profile = StudentProfile(**profile_data) if profile_data else None

        ppt, source = await self._generate_ppt(topic, profile)

        return {
            "ppt_deck": ppt.model_dump(),
            "messages": [
                {"role": "assistant", "content": f"【PPT课件】{ppt.topic} | 共{ppt.total_slides}页（来源: {source}）"},
                {"role": "assistant", "content": ppt.to_markdown()}
            ],
        }

    def _extract_topic(self, state: dict[str, Any]) -> str:
        if state.get("learning_path"):
            lp = LearningPath(**state["learning_path"])
            return lp.path_name
        if state.get("knowledge_tree"):
            return state.get("knowledge_tree", {}).get("topic", "Python学习")
        return state.get("user_input", "Python基础")

    async def _generate_ppt(self, topic: str, profile: StudentProfile | None) -> tuple[PPTDeck, str]:
        if self.spark.configured:
            try:
                return await self._generate_with_spark(topic, profile), "spark"
            except Exception as exc:
                logger.warning("星火PPT生成失败，使用规则兜底: %s", exc)

        return heuristic_ppt(topic, profile), "heuristic"

    async def _generate_with_spark(self, topic: str, profile: StudentProfile | None) -> PPTDeck:
        system_prompt = load_ppt_prompt()
        level = profile.knowledge_level if profile else "beginner"
        style = profile.learning_style if profile else "reading"

        user_prompt = (
            f"请为主题「{topic}」生成PPT课件，"
            f"难度等级：{level}，学习风格：{style}，"
            f"输出严格JSON格式：topic, total_slides, slides(含slide_number,title,content数组,notes)"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        data = await self.spark.chat_json(messages)
        data["source"] = "spark"
        return PPTDeck.model_validate(data)