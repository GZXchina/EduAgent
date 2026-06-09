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


# ---------------------------------------------------------------------------
# 学科模板：基于主题关键词匹配，生成更贴合学科的兜底思维导图
# ---------------------------------------------------------------------------

_PROGRAMMING_KEYWORDS = {
    "python", "java", "javascript", "c++", "编程", "代码", "程序", "算法",
    "数据结构", "函数", "面向对象", "循环", "递归", "排序", "链表", "树",
    "图", "数据库", "sql", "api", "框架", "前端", "后端", "web",
}

_MATH_KEYWORDS = {
    "数学", "微积分", "线性代数", "概率", "统计", "几何", "代数",
    "函数", "方程", "矩阵", "向量", "极限", "导数", "积分", "数列",
}

_SCIENCE_KEYWORDS = {
    "物理", "化学", "生物", "力学", "电磁", "光学", "热力学",
    "有机", "无机", "细胞", "基因", "进化", "实验", "量子",
}


def _detect_discipline(topic: str) -> str:
    """根据主题关键词检测学科类型。"""
    topic_lower = topic.lower()
    if any(kw in topic_lower for kw in _PROGRAMMING_KEYWORDS):
        return "programming"
    if any(kw in topic_lower for kw in _MATH_KEYWORDS):
        return "math"
    if any(kw in topic_lower for kw in _SCIENCE_KEYWORDS):
        return "science"
    return "default"


def _heuristic_programming(topic: str, level: str) -> MindMapNode:
    """编程类学科模板。"""
    if level == "advanced":
        return MindMapNode(
            id="root", text=topic,
            children=[
                MindMapNode(id="arch", text="架构设计", icon="📖", children=[
                    MindMapNode(id="a1", text="设计模式", icon="⚙️"),
                    MindMapNode(id="a2", text="SOLID原则", icon="💡"),
                    MindMapNode(id="a3", text="系统架构", icon="🔗"),
                ]),
                MindMapNode(id="perf", text="性能优化", icon="⚙️", children=[
                    MindMapNode(id="p1", text="算法复杂度", icon="📖", note="时间与空间权衡"),
                    MindMapNode(id="p2", text="内存管理", icon="⚠️"),
                    MindMapNode(id="p3", text="并发编程", icon="💡"),
                ]),
                MindMapNode(id="eng", text="工程实践", icon="⚙️", children=[
                    MindMapNode(id="e1", text="CI/CD流水线"),
                    MindMapNode(id="e2", text="测试策略", icon="🎯"),
                    MindMapNode(id="e3", text="代码审查"),
                ]),
                MindMapNode(id="frontier", text="前沿方向", icon="🔗", children=[
                    MindMapNode(id="f1", text="云原生"),
                    MindMapNode(id="f2", text="AI工程化"),
                ]),
            ],
        )
    elif level == "intermediate":
        return MindMapNode(
            id="root", text=topic,
            children=[
                MindMapNode(id="concept", text="核心概念", icon="📖", children=[
                    MindMapNode(id="c1", text="基本原理"),
                    MindMapNode(id="c2", text="关键语法", icon="⚙️"),
                    MindMapNode(id="c3", text="数据结构", note="选择合适数据结构是关键"),
                ]),
                MindMapNode(id="impl", text="实现细节", icon="⚙️", children=[
                    MindMapNode(id="i1", text="编码规范", icon="💡"),
                    MindMapNode(id="i2", text="调试技巧", icon="⚠️"),
                    MindMapNode(id="i3", text="错误处理"),
                ]),
                MindMapNode(id="practice", text="实践应用", icon="🎯", children=[
                    MindMapNode(id="p1", text="项目实战"),
                    MindMapNode(id="p2", text="常见问题", icon="⚠️"),
                    MindMapNode(id="p3", text="最佳实践", icon="💡"),
                ]),
            ],
        )
    else:
        return MindMapNode(
            id="root", text=topic,
            children=[
                MindMapNode(id="intro", text="入门概述", icon="📖", children=[
                    MindMapNode(id="i1", text=f"什么是{topic}"),
                    MindMapNode(id="i2", text="学习意义"),
                    MindMapNode(id="i3", text="应用领域"),
                ]),
                MindMapNode(id="basics", text="基础语法", icon="⚙️", children=[
                    MindMapNode(id="b1", text="基本概念"),
                    MindMapNode(id="b2", text="简单示例", icon="💡"),
                    MindMapNode(id="b3", text="常见错误", icon="⚠️", note="初学者最容易犯的错"),
                ]),
                MindMapNode(id="practice", text="动手练习", icon="🎯", children=[
                    MindMapNode(id="p1", text="基础练习"),
                    MindMapNode(id="p2", text="小项目"),
                ]),
            ],
        )


def _heuristic_math(topic: str, level: str) -> MindMapNode:
    """数学类学科模板。"""
    if level == "advanced":
        return MindMapNode(
            id="root", text=topic,
            children=[
                MindMapNode(id="theory", text="理论基础", icon="📖", children=[
                    MindMapNode(id="t1", text="公理体系"),
                    MindMapNode(id="t2", text="核心定理", icon="💡"),
                    MindMapNode(id="t3", text="严格证明", icon="⚙️"),
                ]),
                MindMapNode(id="extend", text="拓展理论", icon="🔗", children=[
                    MindMapNode(id="e1", text="推广形式"),
                    MindMapNode(id="e2", text="相关领域"),
                    MindMapNode(id="e3", text="未解问题", icon="🎯"),
                ]),
                MindMapNode(id="apply", text="前沿应用", icon="🎯", children=[
                    MindMapNode(id="a1", text="工程应用"),
                    MindMapNode(id="a2", text="交叉学科"),
                ]),
            ],
        )
    elif level == "intermediate":
        return MindMapNode(
            id="root", text=topic,
            children=[
                MindMapNode(id="def", text="定义与概念", icon="📖", children=[
                    MindMapNode(id="d1", text="核心定义"),
                    MindMapNode(id="d2", text="关键性质", icon="💡"),
                    MindMapNode(id="d3", text="几何意义", note="直观理解很重要"),
                ]),
                MindMapNode(id="method", text="计算方法", icon="⚙️", children=[
                    MindMapNode(id="m1", text="基本方法"),
                    MindMapNode(id="m2", text="技巧总结", icon="💡"),
                    MindMapNode(id="m3", text="易错点", icon="⚠️"),
                ]),
                MindMapNode(id="apply", text="应用场景", icon="🎯", children=[
                    MindMapNode(id="a1", text="典型例题"),
                    MindMapNode(id="a2", text="实际应用"),
                ]),
            ],
        )
    else:
        return MindMapNode(
            id="root", text=topic,
            children=[
                MindMapNode(id="intro", text="基本概念", icon="📖", children=[
                    MindMapNode(id="i1", text=f"什么是{topic}"),
                    MindMapNode(id="i2", text="直观理解"),
                    MindMapNode(id="i3", text="简单例子", icon="💡"),
                ]),
                MindMapNode(id="basic", text="基础运算", icon="⚙️", children=[
                    MindMapNode(id="b1", text="基本公式"),
                    MindMapNode(id="b2", text="计算步骤"),
                    MindMapNode(id="b3", text="常见错误", icon="⚠️"),
                ]),
                MindMapNode(id="practice", text="练习巩固", icon="🎯", children=[
                    MindMapNode(id="p1", text="基础题"),
                    MindMapNode(id="p2", text="应用题"),
                ]),
            ],
        )


def _heuristic_science(topic: str, level: str) -> MindMapNode:
    """理工科（物理/化学/生物）模板。"""
    if level == "advanced":
        return MindMapNode(
            id="root", text=topic,
            children=[
                MindMapNode(id="theory", text="理论框架", icon="📖", children=[
                    MindMapNode(id="t1", text="核心定律", icon="💡"),
                    MindMapNode(id="t2", text="数学推导"),
                    MindMapNode(id="t3", text="理论边界", icon="⚠️"),
                ]),
                MindMapNode(id="exp", text="实验研究", icon="⚙️", children=[
                    MindMapNode(id="e1", text="实验设计"),
                    MindMapNode(id="e2", text="数据分析"),
                    MindMapNode(id="e3", text="误差分析", icon="⚠️"),
                ]),
                MindMapNode(id="frontier", text="前沿进展", icon="🔗", children=[
                    MindMapNode(id="f1", text="最新发现"),
                    MindMapNode(id="f2", text="技术突破"),
                ]),
            ],
        )
    elif level == "intermediate":
        return MindMapNode(
            id="root", text=topic,
            children=[
                MindMapNode(id="principle", text="基本原理", icon="📖", children=[
                    MindMapNode(id="p1", text="核心概念"),
                    MindMapNode(id="p2", text="重要定律", icon="💡"),
                    MindMapNode(id="p3", text="适用条件", icon="⚠️"),
                ]),
                MindMapNode(id="method", text="研究方法", icon="⚙️", children=[
                    MindMapNode(id="m1", text="实验方法"),
                    MindMapNode(id="m2", text="计算模拟"),
                    MindMapNode(id="m3", text="数据分析"),
                ]),
                MindMapNode(id="apply", text="实际应用", icon="🎯", children=[
                    MindMapNode(id="a1", text="工程应用"),
                    MindMapNode(id="a2", text="生活实例"),
                ]),
            ],
        )
    else:
        return MindMapNode(
            id="root", text=topic,
            children=[
                MindMapNode(id="intro", text="概述", icon="📖", children=[
                    MindMapNode(id="i1", text=f"什么是{topic}"),
                    MindMapNode(id="i2", text="生活中的例子", icon="💡"),
                    MindMapNode(id="i3", text="学习意义"),
                ]),
                MindMapNode(id="basic", text="基础知识", icon="⚙️", children=[
                    MindMapNode(id="b1", text="基本概念"),
                    MindMapNode(id="b2", text="简单实验", icon="🎯"),
                    MindMapNode(id="b3", text="常见误解", icon="⚠️"),
                ]),
                MindMapNode(id="practice", text="动手探究", icon="🎯", children=[
                    MindMapNode(id="p1", text="观察实验"),
                    MindMapNode(id="p2", text="思考问题"),
                ]),
            ],
        )


def _heuristic_default(topic: str, level: str) -> MindMapNode:
    """通用学科模板。"""
    if level == "advanced":
        return MindMapNode(
            id="root", text=topic,
            children=[
                MindMapNode(id="theory", text="理论框架", icon="📖", children=[
                    MindMapNode(id="t1", text="核心理论", icon="💡"),
                    MindMapNode(id="t2", text="学术前沿"),
                    MindMapNode(id="t3", text="批判性思考", icon="⚠️"),
                ]),
                MindMapNode(id="method", text="研究方法", icon="⚙️", children=[
                    MindMapNode(id="m1", text="方法论"),
                    MindMapNode(id="m2", text="分析工具"),
                    MindMapNode(id="m3", text="评估体系"),
                ]),
                MindMapNode(id="apply", text="深度应用", icon="🎯", children=[
                    MindMapNode(id="a1", text="行业案例"),
                    MindMapNode(id="a2", text="创新方向", icon="🔗"),
                ]),
            ],
        )
    elif level == "intermediate":
        return MindMapNode(
            id="root", text=topic,
            children=[
                MindMapNode(id="concept", text="核心概念", icon="📖", children=[
                    MindMapNode(id="c1", text="基本原理"),
                    MindMapNode(id="c2", text="关键术语"),
                    MindMapNode(id="c3", text="知识框架", note="建立整体认知很重要"),
                ]),
                MindMapNode(id="deep", text="深入理解", icon="⚙️", children=[
                    MindMapNode(id="d1", text="底层逻辑", icon="💡"),
                    MindMapNode(id="d2", text="实现细节"),
                    MindMapNode(id="d3", text="常见误区", icon="⚠️"),
                ]),
                MindMapNode(id="practice", text="实践应用", icon="🎯", children=[
                    MindMapNode(id="p1", text="典型场景"),
                    MindMapNode(id="p2", text="案例分析"),
                    MindMapNode(id="p3", text="问题解决"),
                ]),
            ],
        )
    else:
        return MindMapNode(
            id="root", text=topic,
            children=[
                MindMapNode(id="intro", text="入门概述", icon="📖", children=[
                    MindMapNode(id="i1", text=f"什么是{topic}"),
                    MindMapNode(id="i2", text="学习意义"),
                    MindMapNode(id="i3", text="应用领域"),
                ]),
                MindMapNode(id="basics", text="基础知识", icon="⚙️", children=[
                    MindMapNode(id="b1", text="核心概念"),
                    MindMapNode(id="b2", text="基本原理", icon="💡"),
                    MindMapNode(id="b3", text="常见问题", icon="⚠️"),
                ]),
                MindMapNode(id="practice", text="初步实践", icon="🎯", children=[
                    MindMapNode(id="p1", text="基础练习"),
                    MindMapNode(id="p2", text="简单项目"),
                ]),
            ],
        )


_DISCIPLINE_BUILDERS = {
    "programming": _heuristic_programming,
    "math": _heuristic_math,
    "science": _heuristic_science,
    "default": _heuristic_default,
}


def heuristic_mindmap(topic: str, profile: StudentProfile | None = None) -> MindMap:
    """星火未配置时的规则兜底思维导图生成。基于学科分类和知识水平生成更贴合的模板。"""
    level = profile.knowledge_level if profile else "beginner"
    discipline = _detect_discipline(topic)
    builder = _DISCIPLINE_BUILDERS.get(discipline, _heuristic_default)
    root = builder(topic, level)
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
                {"role": "assistant", "content": mindmap.to_markdown()},
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
                return await self._generate_with_spark(topic, profile, model), "spark"
            except Exception as exc:
                logger.warning("星火思维导图生成失败，使用规则兜底: %s", exc)

        return heuristic_mindmap(topic, profile), "heuristic"

    async def _generate_with_spark(
        self, topic: str, profile: StudentProfile | None, model: str | None = None
    ) -> MindMap:
        system_prompt = load_mindmap_prompt()

        level = profile.knowledge_level if profile else "beginner"
        user_prompt = (
            f"请为主题「{topic}」生成思维导图，"
            f"学习者知识水平：{level}。"
            f"输出JSON格式：topic, root(含id,text,children,icon?,note?,style?递归结构)"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        data = await self.spark.chat_json(messages, model=model)
        data["source"] = "spark"
        return MindMap.model_validate(data)
