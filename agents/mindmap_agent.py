from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from backend.integrations.spark.client import get_spark_client
from schemas.profile import LearningPath, MindMap, MindMapNode, StudentProfile

logger = logging.getLogger(__name__)


def _prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts" / "mindmap_agent.md"


def load_mindmap_prompt() -> str:
    path = _prompt_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "你是思维导图生成助手，根据学习主题生成知识结构图。"


def heuristic_mindmap(topic: str, profile: StudentProfile | None = None) -> MindMap:
    """星火未配置时的规则兜底思维导图生成。"""

    if "循环" in topic or "loop" in topic.lower():
        return _generate_loop_mindmap()
    elif "函数" in topic or "function" in topic.lower():
        return _generate_function_mindmap()
    elif "面向对象" in topic or "oop" in topic.lower():
        return _generate_oop_mindmap()
    else:
        return _generate_generic_mindmap(topic)


def _generate_loop_mindmap() -> MindMap:
    root = MindMapNode(
        id="loop",
        text="Python循环结构",
        children=[
            MindMapNode(
                id="for_loop",
                text="for循环",
                children=[
                    MindMapNode(id="for_range", text="range函数"),
                    MindMapNode(id="for_list", text="遍历列表"),
                    MindMapNode(id="for_enumerate", text="enumerate"),
                ]
            ),
            MindMapNode(
                id="while_loop",
                text="while循环",
                children=[
                    MindMapNode(id="while_cond", text="条件判断"),
                    MindMapNode(id="while_infinite", text="避免死循环"),
                ]
            ),
            MindMapNode(
                id="loop_control",
                text="循环控制",
                children=[
                    MindMapNode(id="break", text="break退出"),
                    MindMapNode(id="continue", text="continue跳过"),
                    MindMapNode(id="pass", text="pass占位"),
                ]
            ),
            MindMapNode(
                id="nested_loop",
                text="嵌套循环",
                children=[
                    MindMapNode(id="nested_2d", text="二维数组遍历"),
                    MindMapNode(id="nested_pattern", text="图案打印"),
                ]
            ),
        ]
    )
    return MindMap(topic="Python循环结构", root=root, source="heuristic")


def _generate_function_mindmap() -> MindMap:
    root = MindMapNode(
        id="function",
        text="Python函数",
        children=[
            MindMapNode(
                id="func_def",
                text="函数定义",
                children=[
                    MindMapNode(id="def_keyword", text="def关键字"),
                    MindMapNode(id="func_name", text="函数命名"),
                    MindMapNode(id="func_params", text="参数列表"),
                ]
            ),
            MindMapNode(
                id="func_args",
                text="函数参数",
                children=[
                    MindMapNode(id="positional", text="位置参数"),
                    MindMapNode(id="keyword", text="关键字参数"),
                    MindMapNode(id="default", text="默认参数"),
                    MindMapNode(id="variadic", text="可变参数"),
                ]
            ),
            MindMapNode(
                id="func_return",
                text="返回值",
                children=[
                    MindMapNode(id="return_single", text="返回单个值"),
                    MindMapNode(id="return_multiple", text="返回多个值"),
                    MindMapNode(id="return_none", text="返回None"),
                ]
            ),
            MindMapNode(
                id="func_scope",
                text="作用域",
                children=[
                    MindMapNode(id="local", text="局部变量"),
                    MindMapNode(id="global", text="全局变量"),
                    MindMapNode(id="nonlocal", text="nonlocal"),
                ]
            ),
            MindMapNode(
                id="advanced",
                text="高级特性",
                children=[
                    MindMapNode(id="lambda", text="lambda表达式"),
                    MindMapNode(id="closure", text="闭包"),
                    MindMapNode(id="decorator", text="装饰器"),
                    MindMapNode(id="recursion", text="递归"),
                ]
            ),
        ]
    )
    return MindMap(topic="Python函数", root=root, source="heuristic")


def _generate_oop_mindmap() -> MindMap:
    root = MindMapNode(
        id="oop",
        text="面向对象编程",
        children=[
            MindMapNode(
                id="class_def",
                text="类定义",
                children=[
                    MindMapNode(id="class_keyword", text="class关键字"),
                    MindMapNode(id="init_method", text="__init__方法"),
                    MindMapNode(id="self_param", text="self参数"),
                ]
            ),
            MindMapNode(
                id="class_attr",
                text="类属性",
                children=[
                    MindMapNode(id="instance_attr", text="实例属性"),
                    MindMapNode(id="class_attr", text="类属性"),
                    MindMapNode(id="private_attr", text="私有属性"),
                ]
            ),
            MindMapNode(
                id="class_method",
                text="类方法",
                children=[
                    MindMapNode(id="instance_method", text="实例方法"),
                    MindMapNode(id="classmethod", text="类方法"),
                    MindMapNode(id="staticmethod", text="静态方法"),
                ]
            ),
            MindMapNode(
                id="inheritance",
                text="继承",
                children=[
                    MindMapNode(id="single_inherit", text="单继承"),
                    MindMapNode(id="multiple_inherit", text="多继承"),
                    MindMapNode(id="super_func", text="super()函数"),
                ]
            ),
            MindMapNode(
                id="oop_features",
                text="OOP特性",
                children=[
                    MindMapNode(id="encapsulation", text="封装"),
                    MindMapNode(id="inheritance_oop", text="继承"),
                    MindMapNode(id="polymorphism", text="多态"),
                ]
            ),
        ]
    )
    return MindMap(topic="Python面向对象编程", root=root, source="heuristic")


def _generate_generic_mindmap(topic: str) -> MindMap:
    root = MindMapNode(
        id="root",
        text=topic,
        children=[
            MindMapNode(
                id="concept",
                text="基本概念",
                children=[
                    MindMapNode(id="def1", text="定义1"),
                    MindMapNode(id="def2", text="定义2"),
                ]
            ),
            MindMapNode(
                id="syntax",
                text="语法特性",
                children=[
                    MindMapNode(id="syn1", text="语法点1"),
                    MindMapNode(id="syn2", text="语法点2"),
                ]
            ),
            MindMapNode(
                id="usage",
                text="使用方法",
                children=[
                    MindMapNode(id="use1", text="使用场景1"),
                    MindMapNode(id="use2", text="使用场景2"),
                ]
            ),
            MindMapNode(
                id="example",
                text="实例应用",
                children=[
                    MindMapNode(id="exp1", text="案例1"),
                    MindMapNode(id="exp2", text="案例2"),
                ]
            ),
        ]
    )
    return MindMap(topic=topic, root=root, source="heuristic")


class MindMapAgent(BaseAgent):
    """思维导图Agent：根据学习主题生成知识结构图。"""

    name = "mindmap"

    def __init__(self) -> None:
        self.spark = get_spark_client()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        topic = self._extract_topic(state)
        profile_data = state.get("student_profile", {})
        profile = StudentProfile(**profile_data) if profile_data else None

        mindmap, source = await self._generate_mindmap(topic, profile)

        return {
            "mindmap": mindmap.model_dump(),
            "messages": [
                {"role": "assistant", "content": f"【思维导图】{mindmap.topic}（来源: {source}）"},
                {"role": "assistant", "content": "```mermaid\n" + mindmap.to_mermaid() + "\n```"},
                {"role": "assistant", "content": mindmap.to_markdown()}
            ],
        }

    def _extract_topic(self, state: dict[str, Any]) -> str:
        if state.get("learning_path"):
            lp = LearningPath(**state["learning_path"])
            return lp.path_name
        return state.get("user_input", "Python基础")

    async def _generate_mindmap(self, topic: str, profile: StudentProfile | None) -> tuple[MindMap, str]:
        if self.spark.configured:
            try:
                return await self._generate_with_spark(topic), "spark"
            except Exception as exc:
                logger.warning("星火思维导图生成失败，使用规则兜底: %s", exc)

        return heuristic_mindmap(topic, profile), "heuristic"

    async def _generate_with_spark(self, topic: str) -> MindMap:
        system_prompt = load_mindmap_prompt()

        user_prompt = (
            f"请为主题「{topic}」生成思维导图，"
            f"输出JSON格式：topic, root(含id,text,children递归结构)"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        data = await self.spark.chat_json(messages)
        data["source"] = "spark"
        return MindMap.model_validate(data)