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
    """星火未配置时的规则兜底视频脚本生成。"""

    if "循环" in topic or "loop" in topic.lower():
        return _generate_loop_video()
    elif "函数" in topic or "function" in topic.lower():
        return _generate_function_video()
    elif "面向对象" in topic or "oop" in topic.lower():
        return _generate_oop_video()
    else:
        return _generate_generic_video(topic)


def _generate_loop_video() -> VideoScript:
    scenes = [
        VideoScriptScene(
            scene_number=1,
            duration="1分钟",
            content="开场：自我介绍，引出今天的主题——Python循环",
            visual_description="PPT封面，显示课程标题和讲师名字",
            audio_notes="语调活泼，吸引注意力"
        ),
        VideoScriptScene(
            scene_number=2,
            duration="2分钟",
            content="概念讲解：什么是循环，为什么要使用循环",
            visual_description="动画演示：没有循环时重复打印5次的代码 vs 有循环的代码",
            audio_notes="详细解释循环的作用和优势"
        ),
        VideoScriptScene(
            scene_number=3,
            duration="3分钟",
            content="for循环讲解：语法结构、range函数使用",
            visual_description="代码演示，IDE窗口，分步执行highlight",
            audio_notes="边讲边敲代码，重点解释range()的三个参数"
        ),
        VideoScriptScene(
            scene_number=4,
            duration="2分钟",
            content="while循环讲解：条件控制、需要注意的事项",
            visual_description="代码演示，强调条件判断的重要性",
            audio_notes="提醒死循环的风险和调试方法"
        ),
        VideoScriptScene(
            scene_number=5,
            duration="3分钟",
            content="实战演示：打印九九乘法表",
            visual_description="完整代码编写过程，最后展示运行结果",
            audio_notes="完整展示一个实际应用案例"
        ),
        VideoScriptScene(
            scene_number=6,
            duration="2分钟",
            content="常见错误与调试技巧",
            visual_description="错误代码示例，调试过程演示",
            audio_notes="总结常见错误和解决方法"
        ),
        VideoScriptScene(
            scene_number=7,
            duration="1分钟",
            content="总结本节内容，布置课后练习",
            visual_description="PPT总结页，显示要点和练习题",
            audio_notes="回顾重点，预告下节内容"
        ),
    ]
    return VideoScript(
        topic="Python循环结构",
        total_duration="14分钟",
        scenes=scenes,
        suggestions=[
            "建议语速适中，给观众思考时间",
            "代码演示时字体要大，方便看清",
            "关键知识点要重复强调"
        ],
        source="heuristic"
    )


def _generate_function_video() -> VideoScript:
    scenes = [
        VideoScriptScene(
            scene_number=1,
            duration="1分钟",
            content="开场：回顾上节内容，引出新主题——函数",
            visual_description="PPT封面，快速回顾上节要点",
            audio_notes="承上启下，自然过渡"
        ),
        VideoScriptScene(
            scene_number=2,
            duration="2分钟",
            content="函数概念：什么是函数，函数的好处",
            visual_description="图解：函数的定义和调用过程",
            audio_notes="用生活例子解释函数的概念"
        ),
        VideoScriptScene(
            scene_number=3,
            duration="3分钟",
            content="函数定义：def关键字，参数传递，返回值",
            visual_description="代码演示，多个简单函数示例",
            audio_notes="详细讲解每个部分的作用"
        ),
        VideoScriptScene(
            scene_number=4,
            duration="2分钟",
            content="参数类型：位置参数、关键字参数、默认参数",
            visual_description="代码演示不同参数调用方式",
            audio_notes="对比讲解，加深理解"
        ),
        VideoScriptScene(
            scene_number=5,
            duration="3分钟",
            content="实战：编写一个学生成绩处理函数",
            visual_description="完整项目代码，从需求到实现",
            audio_notes="综合应用所学知识"
        ),
        VideoScriptScene(
            scene_number=6,
            duration="2分钟",
            content="递归函数简介：递归的概念和终止条件",
            visual_description="动画演示递归调用过程",
            audio_notes="用阶乘举例，画图说明"
        ),
        VideoScriptScene(
            scene_number=7,
            duration="1分钟",
            content="总结与练习",
            visual_description="PPT总结页",
            audio_notes="回顾重点，布置作业"
        ),
    ]
    return VideoScript(
        topic="Python函数",
        total_duration="14分钟",
        scenes=scenes,
        suggestions=[
            "函数是编程核心，讲透彻很重要",
            "多举例，用生活例子帮助理解",
            "递归部分可以用动画辅助"
        ],
        source="heuristic"
    )


def _generate_oop_video() -> VideoScript:
    scenes = [
        VideoScriptScene(
            scene_number=1,
            duration="1分钟",
            content="开场：从面向过程过渡到面向对象",
            visual_description="对比图：面向过程 vs 面向对象",
            audio_notes="解释两种编程范式的区别"
        ),
        VideoScriptScene(
            scene_number=2,
            duration="2分钟",
            content="类与对象：概念讲解，生活中的类比",
            visual_description="图解：类就像蓝图，对象是实例",
            audio_notes="用汽车设计图纸做类比"
        ),
        VideoScriptScene(
            scene_number=3,
            duration="3分钟",
            content="类的定义：class关键字，__init__方法，self参数",
            visual_description="代码演示，定义一个简单的Student类",
            audio_notes="逐行解释代码含义"
        ),
        VideoScriptScene(
            scene_number=4,
            duration="2分钟",
            content="继承：子类继承父类，方法重写",
            visual_description="代码演示：Animal和Dog类",
            audio_notes="演示多态的实际效果"
        ),
        VideoScriptScene(
            scene_number=5,
            duration="3分钟",
            content="实战项目：编写一个简单的银行账户类",
            visual_description="完整代码实现，包含存取方法",
            audio_notes="综合应用OOP特性"
        ),
        VideoScriptScene(
            scene_number=6,
            duration="1分钟",
            content="总结与下节预告",
            visual_description="PPT总结页",
            audio_notes="回顾要点，预告设计模式"
        ),
    ]
    return VideoScript(
        topic="Python面向对象编程",
        total_duration="12分钟",
        scenes=scenes,
        suggestions=[
            "OOP概念较抽象，多用生活实例",
            "代码演示要完整，不要跳步",
            "继承和多态是重点，要讲清楚"
        ],
        source="heuristic"
    )


def _generate_generic_video(topic: str) -> VideoScript:
    scenes = [
        VideoScriptScene(
            scene_number=1,
            duration="1分钟",
            content=f"开场：介绍{topic}",
            visual_description="PPT封面",
            audio_notes="吸引观众兴趣"
        ),
        VideoScriptScene(
            scene_number=2,
            duration="3分钟",
            content=f"概念讲解：{topic}的基本概念",
            visual_description="图解或代码演示",
            audio_notes="详细解释核心概念"
        ),
        VideoScriptScene(
            scene_number=3,
            duration="3分钟",
            content=f"语法讲解：{topic}的语法和使用",
            visual_description="代码演示",
            audio_notes="边讲边敲代码"
        ),
        VideoScriptScene(
            scene_number=4,
            duration="2分钟",
            content=f"实例演示：{topic}的实际应用",
            visual_description="完整项目代码",
            audio_notes="展示实际用途"
        ),
        VideoScriptScene(
            scene_number=5,
            duration="1分钟",
            content="总结与练习",
            visual_description="PPT总结页",
            audio_notes="回顾要点，布置练习"
        ),
    ]
    return VideoScript(
        topic=topic,
        total_duration="10分钟",
        scenes=scenes,
        suggestions=["内容要循序渐进", "多举例帮助理解"],
        source="heuristic"
    )


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
            return lp.path_name
        return state.get("user_input", "Python基础")

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