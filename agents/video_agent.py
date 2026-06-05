from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from backend.integrations.spark.client import get_spark_client
from schemas.profile import LearningPath, VideoScript, VideoScriptScene, StudentProfile

logger = logging.getLogger(__name__)


def _prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts" / "video_agent.md"


def load_video_prompt() -> str:
    path = _prompt_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "你是视频脚本生成助手，根据学习主题生成教学视频脚本。"


def heuristic_video(topic: str, profile: StudentProfile | None = None) -> VideoScript:
    """星火未配置时的规则兜底视频脚本生成。通用模板，适用于任意学科。"""
    level = profile.knowledge_level if profile else "beginner"
    style = profile.learning_style if profile else "reading"

    scenes = _generate_generic_video_scenes(topic, level, style)
    total_min = sum(int(s.duration.replace("分钟", "")) for s in scenes)

    return VideoScript(
        topic=topic,
        total_duration=f"{total_min}分钟",
        scenes=scenes,
        suggestions=[
            "内容要循序渐进，由浅入深",
            "多用生活实例和类比帮助理解",
            "关键知识点要重复强调",
            "语速适中，给观众思考时间",
        ],
        source="heuristic",
    )


def _generate_generic_video_scenes(
    topic: str, level: str, style: str
) -> list[VideoScriptScene]:
    """通用视频脚本生成，按水平和风格调整。"""
    visual_map = {
        "visual": "图解动画和思维导图",
        "auditory": "详细口头讲解和对话",
        "reading": "文字要点和文档演示",
        "kinesthetic": "实际操作和动手演示",
    }
    visual_style = visual_map.get(style, "PPT展示和讲解")

    scenes = [
        VideoScriptScene(
            scene_number=1,
            duration="1分钟",
            content=f"开场：介绍本节主题「{topic}」及其学习意义",
            visual_description="PPT封面，显示主题和学习目标",
            audio_notes="语调亲切活泼，吸引观众注意力",
        ),
        VideoScriptScene(
            scene_number=2,
            duration="3分钟",
            content=f"概念讲解：{topic}的核心概念和基本原理",
            visual_description=f"{visual_style}，展示核心概念的图解",
            audio_notes="用生活实例类比解释抽象概念",
        ),
        VideoScriptScene(
            scene_number=3,
            duration="3分钟",
            content=f"深入讲解：{topic}的关键细节和进阶知识",
            visual_description=f"{visual_style}，分步展示关键知识点",
            audio_notes="详细解释每个要点，强调易错之处",
        ),
        VideoScriptScene(
            scene_number=4,
            duration="3分钟",
            content=f"实战演示：{topic}在实际场景中的应用",
            visual_description=f"{visual_style}，展示完整的应用案例",
            audio_notes="边演示边讲解，突出实际操作步骤",
        ),
        VideoScriptScene(
            scene_number=5,
            duration="2分钟",
            content=f"常见问题：学习{topic}时的常见误区和排查方法",
            visual_description="错误示例对比和正确方法演示",
            audio_notes="总结常见错误，提供解决思路",
        ),
        VideoScriptScene(
            scene_number=6,
            duration="1分钟",
            content="总结与练习：回顾要点，布置课后练习",
            visual_description="PPT总结页，显示要点清单和练习题",
            audio_notes="回顾重点内容，预告下节主题",
        ),
    ]
    return scenes


class VideoAgent(BaseAgent):
    """视频脚本Agent：根据学习主题生成教学视频脚本。"""

    name = "video"

    def __init__(self) -> None:
        self.spark = get_spark_client()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        topic = self._extract_topic(state)
        profile_data = state.get("student_profile", {})
        profile = StudentProfile(**profile_data) if profile_data else None

        video_script, source = await self._generate_video(topic, profile)

        return {
            "video_script": video_script.model_dump(),
            "messages": [
                {"role": "assistant", "content": f"【视频脚本】{video_script.topic} | 时长{video_script.total_duration}（来源: {source}）"},
                {"role": "assistant", "content": video_script.to_markdown()}
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

    async def _generate_video(self, topic: str, profile: StudentProfile | None) -> tuple[VideoScript, str]:
        if self.spark.configured:
            try:
                return await self._generate_with_spark(topic), "spark"
            except Exception as exc:
                logger.warning("星火视频脚本生成失败，使用规则兜底: %s", exc)

        return heuristic_video(topic, profile), "heuristic"

    async def _generate_with_spark(self, topic: str) -> VideoScript:
        system_prompt = load_video_prompt()

        user_prompt = (
            f"请为主题「{topic}」生成教学视频脚本，"
            f"输出JSON格式：topic, total_duration, scenes(含scene_number,duration,content,visual_description,audio_notes), suggestions"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        data = await self.spark.chat_json(messages)
        data["source"] = "spark"
        return VideoScript.model_validate(data)