from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from backend.integrations.spark.client import get_spark_client
from rag.retriever import KnowledgeRetriever
from schemas.profile import LearningPath, StudentProfile

logger = logging.getLogger(__name__)


def _prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts" / "knowledge_agent.md"


def load_knowledge_prompt() -> str:
    path = _prompt_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "你是知识拆解助手，根据学习主题和RAG检索结果生成结构化知识树。"


def heuristic_knowledge_tree(topic: str, profile: StudentProfile | None = None) -> dict[str, Any]:
    """星火未配置时的规则兜底知识拆解。
    生成通用的结构化知识树，内容围绕用户实际主题而非硬编码特定学科。
    """
    level = profile.knowledge_level if profile else "beginner"

    # 根据水平层级决定知识深度结构（通用模板，适用于任何学科）
    if level == "advanced":
        nodes = [
            {"id": "adv_1", "title": f"{topic}核心理论", "children": ["理论框架", "基本原理", "数学/逻辑基础"]},
            {"id": "adv_2", "title": f"{topic}高级特性", "children": ["高级机制", "优化技巧", "设计模式"]},
            {"id": "adv_3", "title": f"{topic}实践应用", "children": ["真实项目案例", "性能调优", "最佳实践"]},
            {"id": "adv_4", "title": f"{topic}前沿探索", "children": ["最新发展", "研究方向", "论文/资料研读"]},
        ]
    elif level == "intermediate":
        nodes = [
            {"id": "mid_1", "title": f"{topic}基础回顾", "children": ["核心概念", "常见误区", "知识梳理"]},
            {"id": "mid_2", "title": f"{topic}深入理解", "children": ["进阶知识点", "底层原理", "实现细节"]},
            {"id": "mid_3", "title": f"{topic}实际应用", "children": ["典型场景", "案例分析", "问题解决"]},
            {"id": "mid_4", "title": f"{topic}综合提升", "children": ["跨领域关联", "系统性思维", "项目实战"]},
        ]
    else:
        # beginner：从入门到基础实践
        nodes = [
            {"id": "beg_1", "title": f"{topic}入门概述", "children": ["什么是" + topic, "学习意义", "应用领域"]},
            {"id": "beg_2", "title": f"{topic}基础知识", "children": ["核心概念", "基本术语", "入门工具/环境"]},
            {"id": "beg_3", "title": f"{topic}基本操作", "children": ["基本使用方法", "简单示例", "常见问题"]},
            {"id": "beg_4", "title": f"{topic}初步实践", "children": ["基础练习", "简单项目", "错误排查"]},
        ]

    return {
        "topic": topic,
        "level": level,
        "nodes": nodes,
        "source": "heuristic",
    }


class KnowledgeAgent(BaseAgent):
    """知识拆解Agent：根据学习主题从RAG检索知识并生成结构化知识树。"""

    name = "knowledge"

    def __init__(self) -> None:
        self.spark = get_spark_client()
        self.retriever = KnowledgeRetriever()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        topic = self._extract_topic(state)
        profile_data = state.get("student_profile", {})
        profile = StudentProfile(**profile_data) if profile_data else None

        knowledge_tree, source = await self._generate_knowledge_tree(topic, profile)

        return {
            "knowledge_tree": knowledge_tree,
            "messages": [
                {"role": "assistant", "content": f"【知识拆解】{knowledge_tree['topic']} | 包含{len(knowledge_tree['nodes'])}个主要节点（来源: {source}）"},
            ],
        }

    def _extract_topic(self, state: dict[str, Any]) -> str:
        # 优先从学习路径中提取真实主题名称
        if state.get("learning_path"):
            lp = LearningPath(**state["learning_path"])
            if lp.path_name and lp.path_name != "unknown":
                return lp.path_name
        # 从画像中提取专业/学习目标
        profile_data = state.get("student_profile", {})
        if profile_data:
            profile = StudentProfile(**profile_data)
            if profile.learning_goal_text and profile.learning_goal_text not in ("unknown", ""):
                return profile.learning_goal_text[:30]
            if profile.major and profile.major not in ("", "unknown"):
                return profile.major
        # 最后使用用户输入
        user_input = state.get("user_input", "")
        return user_input[:30] if user_input else "通用学习"

    def _format_tree_markdown(self, tree: dict[str, Any]) -> str:
        lines = [f"## 📚 {tree['topic']} 知识结构\n"]
        for node in tree.get("nodes", []):
            lines.append(f"### {node['title']}")
            for child in node.get("children", []):
                lines.append(f"- {child}")
            lines.append("")
        return "\n".join(lines)

    async def _generate_knowledge_tree(self, topic: str, profile: StudentProfile | None) -> tuple[dict[str, Any], str]:
        if self.spark.configured:
            try:
                docs = await self.retriever.query(topic, k=5)
                if docs:
                    return await self._generate_with_spark(topic, docs, profile), "spark"
            except Exception as exc:
                logger.warning("星火知识拆解失败，使用规则兜底: %s", exc)

        return heuristic_knowledge_tree(topic, profile), "heuristic"

    async def _generate_with_spark(self, topic: str, docs: list[dict[str, Any]], profile: StudentProfile | None) -> dict[str, Any]:
        system_prompt = load_knowledge_prompt()
        level = profile.knowledge_level if profile else "beginner"

        # 构建 RAG 上下文（增加检索数量和每段长度）
        rag_lines = []
        for doc in docs[:5]:
            content = doc.get("content", "").strip()
            if content:
                rag_lines.append(f"- {content[:500]}")
        context = "\n".join(rag_lines) if rag_lines else "（无检索结果）"

        # 构建画像上下文
        profile_context = ""
        if profile:
            parts = [f"知识水平：{level}"]
            if profile.major:
                parts.append(f"专业/学科：{profile.major}")
            if profile.learning_goal_text and profile.learning_goal_text not in ("unknown", ""):
                parts.append(f"学习目标：{profile.learning_goal_text}")
            if profile.weakness:
                parts.append(f"薄弱点：{profile.weakness}")
            if profile.learning_style and profile.learning_style != "unknown":
                parts.append(f"学习风格：{profile.learning_style}")
            profile_context = "【学生画像】" + " | ".join(parts)

        user_prompt = (
            f"请为主题「{topic}」生成结构化知识树。\n\n"
            f"{profile_context}\n\n"
            f"【重要】知识树的内容必须围绕「{topic}」，不要使用其他学科的内容。\n\n"
            f"【RAG检索到的相关知识】\n{context}\n\n"
            f"输出JSON格式：topic, level, nodes(含id,title,children列表)"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        data = await self.spark.chat_json(messages)
        data["source"] = "spark"
        return data