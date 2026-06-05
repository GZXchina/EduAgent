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
    """星火未配置时的规则兜底思维导图生成。通用模板，适用于任意学科。"""
    level = profile.knowledge_level if profile else "beginner"

    if level == "advanced":
        root = MindMapNode(
            id="root",
            text=topic,
            children=[
                MindMapNode(id="theory", text="理论框架", children=[
                    MindMapNode(id="t1", text="核心定理"),
                    MindMapNode(id="t2", text="数学推导"),
                    MindMapNode(id="t3", text="理论证明"),
                ]),
                MindMapNode(id="advanced_methods", text="高级方法", children=[
                    MindMapNode(id="am1", text="优化算法"),
                    MindMapNode(id="am2", text="对比分析"),
                    MindMapNode(id="am3", text="性能评估"),
                ]),
                MindMapNode(id="applications", text="前沿应用", children=[
                    MindMapNode(id="ap1", text="工业案例"),
                    MindMapNode(id="ap2", text="学术研究"),
                    MindMapNode(id="ap3", text="创新方向"),
                ]),
            ]
        )
    elif level == "intermediate":
        root = MindMapNode(
            id="root",
            text=topic,
            children=[
                MindMapNode(id="concept", text="核心概念", children=[
                    MindMapNode(id="c1", text="基本原理"),
                    MindMapNode(id="c2", text="关键术语"),
                    MindMapNode(id="c3", text="知识框架"),
                ]),
                MindMapNode(id="deep", text="深入理解", children=[
                    MindMapNode(id="d1", text="底层原理"),
                    MindMapNode(id="d2", text="实现细节"),
                    MindMapNode(id="d3", text="常见误区"),
                ]),
                MindMapNode(id="practice", text="实践应用", children=[
                    MindMapNode(id="p1", text="典型场景"),
                    MindMapNode(id="p2", text="案例分析"),
                    MindMapNode(id="p3", text="问题解决"),
                ]),
                MindMapNode(id="advanced", text="进阶提升", children=[
                    MindMapNode(id="a1", text="最佳实践"),
                    MindMapNode(id="a2", text="设计模式"),
                ]),
            ]
        )
    else:
        root = MindMapNode(
            id="root",
            text=topic,
            children=[
                MindMapNode(id="intro", text="入门概述", children=[
                    MindMapNode(id="i1", text="什么是" + topic),
                    MindMapNode(id="i2", text="学习意义"),
                    MindMapNode(id="i3", text="应用领域"),
                ]),
                MindMapNode(id="basics", text="基础知识", children=[
                    MindMapNode(id="b1", text="核心术语"),
                    MindMapNode(id="b2", text="基本原理"),
                    MindMapNode(id="b3", text="入门工具"),
                ]),
                MindMapNode(id="operations", text="基本操作", children=[
                    MindMapNode(id="o1", text="基础使用方法"),
                    MindMapNode(id="o2", text="简单示例"),
                    MindMapNode(id="o3", text="常见问题"),
                ]),
                MindMapNode(id="practice", text="初步实践", children=[
                    MindMapNode(id="pr1", text="基础练习"),
                    MindMapNode(id="pr2", text="简单项目"),
                    MindMapNode(id="pr3", text="错误排查"),
                ]),
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
        model = state.get("model")

        mindmap, source = await self._generate_mindmap(topic, profile, model)

        return {
            "mindmap": mindmap.model_dump(),
            "mindmap_mermaid": mindmap.to_mermaid(),
            "mindmap_markdown": mindmap.to_markdown(),
            "messages": [
                {"role": "assistant", "content": f"【思维导图】{mindmap.topic}（来源: {source}）"},
                {"role": "assistant", "content": "```mermaid\n" + mindmap.to_mermaid() + "\n```"},
                {"role": "assistant", "content": mindmap.to_markdown()}
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

    async def _generate_mindmap(
        self, topic: str, profile: StudentProfile | None, model: str | None = None
    ) -> tuple[MindMap, str]:
        if self.spark.configured:
            try:
                return await self._generate_with_spark(topic, model), "spark"
            except Exception as exc:
                logger.warning("星火思维导图生成失败，使用规则兜底: %s", exc)

        return heuristic_mindmap(topic, profile), "heuristic"

    async def _generate_with_spark(self, topic: str, model: str | None = None) -> MindMap:
        system_prompt = load_mindmap_prompt()

        user_prompt = (
            f"请为主题「{topic}」生成思维导图，"
            f"输出JSON格式：topic, root(含id,text,children递归结构)"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        data = await self.spark.chat_json(messages, model=model)
        data["source"] = "spark"
        return MindMap.model_validate(data)