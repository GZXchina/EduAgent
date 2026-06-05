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
    """星火未配置时的规则兜底PPT生成。通用模板，围绕任意学科主题。"""
    level = profile.knowledge_level if profile else "beginner"
    style = profile.learning_style if profile else "reading"

    slides = _generate_generic_ppt(topic, style, level)

    return PPTDeck(
        topic=topic,
        total_slides=len(slides),
        slides=slides,
        source="heuristic",
    )


def _generate_generic_ppt(topic: str, style: str, level: str) -> list[PPTSlide]:
    """通用PPT生成，按知识水平调整深度，适用于任意学科。"""
    # 根据水平决定页数和内容深度
    if level == "advanced":
        phases = [
            (f"{topic}前沿概述", ["研究背景", "最新进展", "开放问题"]),
            (f"{topic}核心理论", ["理论框架", "数学/逻辑推导", "关键定理"]),
            (f"{topic}高级方法", ["高级技术", "优化策略", "对比分析"]),
            (f"{topic}实践案例", ["工业级案例", "性能评估", "最佳实践"]),
            (f"{topic}前沿探索", ["学术论文解读", "研究方向", "创新思路"]),
            ("总结与展望", ["成果总结", "未来趋势", "参考文献"]),
        ]
    elif level == "intermediate":
        phases = [
            (f"{topic}概述", ["核心概念回顾", "学习目标", "知识框架"]),
            (f"{topic}深入理解", ["进阶知识点", "底层原理", "实现细节"]),
            (f"{topic}实际应用", ["典型场景", "案例分析", "问题解决"]),
            (f"{topic}进阶技巧", ["常见误区", "优化方法", "最佳实践"]),
            (f"{topic}综合项目", ["项目设计", "分步实现", "成果展示"]),
            ("总结与练习", ["知识回顾", "练习题", "拓展学习"]),
        ]
    else:
        phases = [
            (f"{topic}概述", ["概念介绍", "学习意义", "知识框架"]),
            (f"{topic}基础知识", ["核心术语", "基本原理", "入门工具"]),
            (f"{topic}基本操作", ["基础使用方法", "简单示例", "步骤演示"]),
            (f"{topic}常见应用", ["应用场景", "实际案例", "动手练习"]),
            (f"{topic}常见问题", ["常见错误", "排查方法", "注意事项"]),
            (f"{topic}进阶引导", ["进阶方向", "推荐资源", "下一步学习"]),
            ("总结与练习", ["知识点回顾", "练习题", "作业布置"]),
        ]

    # 根据学习风格调整备注
    notes_map = {
        "visual": "配合图解和思维导图展示",
        "auditory": "重点口头讲解，配合音频说明",
        "reading": "提供详细文档和阅读材料",
        "kinesthetic": "配合动手实践和案例操作",
    }
    base_note = notes_map.get(style, "结合讲解与示例")

    slides = []
    for i, (title, content) in enumerate(phases, 1):
        slides.append(PPTSlide(
            slide_number=i,
            title=title,
            content=content,
            notes=base_note if i > 1 else "开场引导，吸引注意力",
        ))
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
            if lp.path_name and lp.path_name != "unknown":
                return lp.path_name
        if state.get("knowledge_tree"):
            kt_topic = state["knowledge_tree"].get("topic", "")
            if kt_topic:
                return kt_topic
        profile_data = state.get("student_profile", {})
        if profile_data:
            p = StudentProfile(**profile_data)
            if p.learning_goal_text and p.learning_goal_text not in ("unknown", ""):
                return p.learning_goal_text[:30]
            if p.major and p.major not in ("", "unknown"):
                return p.major
        user_input = state.get("user_input", "")
        return user_input[:30] if user_input else "通用学习"

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