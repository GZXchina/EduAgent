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
    """星火未配置时的规则兜底知识拆解。"""
    level = profile.knowledge_level if profile else "beginner"

    if "循环" in topic or "loop" in topic.lower():
        nodes = [
            {"id": "loop_1", "title": "循环概念", "children": ["为什么需要循环", "循环的作用"]},
            {"id": "loop_2", "title": "for循环", "children": ["range函数", "遍历列表", "enumerate"]},
            {"id": "loop_3", "title": "while循环", "children": ["条件判断", "避免死循环"]},
            {"id": "loop_4", "title": "循环控制", "children": ["break退出", "continue跳过", "pass占位"]},
            {"id": "loop_5", "title": "嵌套循环", "children": ["二维数组", "图案打印"]},
        ]
    elif "函数" in topic or "function" in topic.lower():
        nodes = [
            {"id": "func_1", "title": "函数基础", "children": ["函数定义", "函数调用", "参数传递"]},
            {"id": "func_2", "title": "参数类型", "children": ["位置参数", "关键字参数", "默认参数", "可变参数"]},
            {"id": "func_3", "title": "返回值", "children": ["返回单个值", "返回多个值", "返回None"]},
            {"id": "func_4", "title": "作用域", "children": ["局部变量", "全局变量", "nonlocal"]},
            {"id": "func_5", "title": "高级特性", "children": ["lambda", "闭包", "装饰器", "递归"]},
        ]
    elif "面向对象" in topic or "oop" in topic.lower():
        nodes = [
            {"id": "oop_1", "title": "类与对象", "children": ["类定义", "__init__", "self参数"]},
            {"id": "oop_2", "title": "类的属性", "children": ["实例属性", "类属性", "私有属性"]},
            {"id": "oop_3", "title": "类的方法", "children": ["实例方法", "类方法", "静态方法"]},
            {"id": "oop_4", "title": "继承", "children": ["单继承", "多继承", "super()"]},
            {"id": "oop_5", "title": "OOP特性", "children": ["封装", "继承", "多态"]},
        ]
    else:
        nodes = [
            {"id": "basic_1", "title": "基本概念", "children": ["定义", "核心原理"]},
            {"id": "basic_2", "title": "语法特性", "children": ["语法点1", "语法点2"]},
            {"id": "basic_3", "title": "使用方法", "children": ["使用场景1", "使用场景2"]},
            {"id": "basic_4", "title": "实例应用", "children": ["案例1", "案例2"]},
        ]

    return {
        "topic": topic,
        "level": level,
        "nodes": nodes,
        "source": "heuristic"
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
                {"role": "assistant", "content": self._format_tree_markdown(knowledge_tree)}
            ],
        }

    def _extract_topic(self, state: dict[str, Any]) -> str:
        if state.get("learning_path"):
            lp = LearningPath(**state["learning_path"])
            return lp.path_name
        return state.get("user_input", "Python基础")

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

        context = "\n".join([f"- {d.get('content', '')[:200]}" for d in docs[:3]])

        user_prompt = (
            f"请根据以下RAG检索到的知识内容，为主题「{topic}」生成结构化知识树。\n"
            f"用户知识水平：{level}\n"
            f"检索到的相关知识：\n{context}\n\n"
            f"输出JSON格式：topic, level, nodes(含id,title,children列表)"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        data = await self.spark.chat_json(messages)
        data["source"] = "spark"
        return data