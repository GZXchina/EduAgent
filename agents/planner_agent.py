from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from backend.integrations.spark.client import get_spark_client
from schemas.profile import LearningPath, LearningStep, StudentProfile

logger = logging.getLogger(__name__)


def _prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts" / "planner_agent.md"


def load_planner_prompt() -> str:
    path = _prompt_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "你是学习规划助手，根据学生画像输出学习路径JSON。"


def _infer_subject(profile: StudentProfile) -> str:
    """从画像中推断用户实际学习的学科/主题。"""
    # 优先从用户的学习目标原文中提取
    if profile.learning_goal_text and profile.learning_goal_text not in ("unknown", ""):
        return profile.learning_goal_text[:30]
    # 其次从专业字段提取
    if profile.major and profile.major not in ("", "unknown"):
        return profile.major
    # 从用户原始输入提取关键词
    if profile.raw_input:
        return profile.raw_input[:30]
    return "通用学习"


def _get_goal_label(goal: str) -> str:
    """将目标标识转为用户可读的标签。"""
    goal_map = {
        "lanqiao_competition": "竞赛备赛",
        "postgraduate_exam": "考研复习",
        "job_preparation": "就业求职",
        "general_learning": "通用学习",
        "certification": "证书考试",
        "research": "学术研究",
    }
    for key, label in goal_map.items():
        if key in goal:
            return label
    return goal if goal and goal != "unknown" else "通用学习"


def _style_to_resources(style: str) -> list[str]:
    """根据学习风格推荐资源类型。"""
    style_map = {
        "visual": ["图解教程", "视频课程", "思维导图"],
        "auditory": ["音频讲解", "视频课程", "播客"],
        "reading": ["文档教程", "电子书", "技术博客"],
        "kinesthetic": ["实践项目", "编程练习", "动手实验"],
    }
    return style_map.get(style, ["文档教程", "视频课程"])


def heuristic_path(profile: StudentProfile) -> LearningPath:
    """星火未配置时的规则兜底学习路径生成。
    根据画像中的实际学科、目标、水平动态生成，不再硬编码特定语言/学科。
    """
    level = profile.knowledge_level
    goal = profile.goal
    weakness = profile.weakness
    study_time = profile.study_time
    subject = _infer_subject(profile)
    goal_label = _get_goal_label(goal)
    base_resources = _style_to_resources(profile.learning_style)

    # 根据目标决定路径名称
    if "lanqiao" in goal or "competition" in goal:
        path_name = f"{subject}竞赛备赛之路"
        focus_areas = ["基础巩固", "竞赛技巧", "真题训练"]
    elif "postgraduate" in goal or "exam" in goal:
        path_name = f"{subject}考研复习之路"
        focus_areas = ["核心知识", "综合应用", "真题演练"]
    elif "job" in goal:
        path_name = f"{subject}就业进阶之路"
        focus_areas = ["项目实战", "技能提升", "面试准备"]
    elif "certification" in goal:
        path_name = f"{subject}证书备考之路"
        focus_areas = ["考纲知识", "真题训练", "模拟测试"]
    else:
        path_name = f"{subject}学习之路"
        focus_areas = ["基础知识", "实践应用"]

    if weakness:
        focus_areas.append(weakness)

    # 根据学习时长确定周数
    weeks = 8
    if study_time == "unknown":
        weeks = 10
    elif "2h" in study_time:
        weeks = 6
    elif "3h" in study_time:
        weeks = 4

    # 根据水平生成分阶段主题（通用模板，不绑定特定学科）
    phase_labels = {
        "beginner": [
            ("基础入门", ["核心概念", "基本术语", "入门工具使用"]),
            ("基础巩固", ["基本语法/规则", "简单案例", "基础练习"]),
            ("初步实践", ["动手练习", "简单项目", "问题排查"]),
            ("知识扩展", ["常用技巧", "进阶语法/规则", "常见模式"]),
            ("综合实践", ["小型项目", "综合练习", "查漏补缺"]),
        ],
        "intermediate": [
            ("知识回顾", ["核心概念回顾", "易错点梳理"]),
            ("深入理解", ["高级特性", "底层原理", "最佳实践"]),
            ("专项突破", ["重点领域深入", "难点攻克"]),
            ("项目实战", ["实际案例分析", "综合项目"]),
            ("进阶提升", ["性能优化", "设计模式", "架构思维"]),
        ],
        "advanced": [
            ("前沿探索", ["最新技术/理论", "行业趋势", "论文研读"]),
            ("深度实践", ["复杂项目", "系统设计", "创新应用"]),
            ("综合评估", ["全面复盘", "成果展示", "经验总结"]),
        ],
    }

    phases = list(phase_labels.get(level, phase_labels["beginner"]))
    # 根据目标类型调整阶段
    if "lanqiao" in goal or "competition" in goal:
        phases.append(("真题特训", ["历年真题", "解题技巧", "时间管理"]))
        phases.append(("模拟冲刺", ["全真模拟", "错题回顾", "考前调整"]))
    elif "postgraduate" in goal or "exam" in goal:
        phases.append(("真题演练", ["历年真题", "考点梳理", "答题技巧"]))
        phases.append(("模拟冲刺", ["全真模拟", "查漏补缺", "考前回顾"]))
    elif "job" in goal:
        phases.append(("面试备战", ["面试题库", "项目复盘", "模拟面试"]))

    steps = []
    for i, (title, topics) in enumerate(phases, 1):
        week_resources = list(base_resources)
        if i == len(phases):
            week_resources = ["模拟测试", "综合评估"]
        elif i == len(phases) - 1:
            week_resources = ["专项训练", "错题本"]

        steps.append(LearningStep(
            week=i,
            title=f"{title}",
            duration="7天",
            topics=topics,
            resources=week_resources,
            assessment="阶段作业" if i < len(phases) else "综合评估",
        ))

    # 根据目标类型调整周数以匹配阶段数
    weeks = len(phases)

    suggestions = [
        f"每天坚持{subject}学习至少30分钟",
        "建立学习笔记，定期回顾",
        "完成每个阶段的评估任务",
    ]
    if weakness:
        suggestions.insert(0, f"重点攻克薄弱点：{weakness}")
    if profile.learning_style == "kinesthetic":
        suggestions.append("多做动手实践项目，边做边学")
    elif profile.learning_style == "visual":
        suggestions.append("多用思维导图整理知识框架")

    return LearningPath(
        path_name=path_name,
        total_weeks=weeks,
        steps=steps,
        focus_areas=focus_areas,
        suggestions=suggestions,
        source="heuristic",
    )


class PlannerAgent(BaseAgent):
    """学习规划 Agent：基于学生画像生成个性化学习路径。"""
    
    name = "planner"
    
    def __init__(self) -> None:
        self.spark = get_spark_client()
    
    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        profile_data = state.get("student_profile", {})
        
        if not profile_data:
            return {
                "learning_path": heuristic_path(StudentProfile()).model_dump(),
                "messages": [{"role": "assistant", "content": f"[{self.name}] 未找到学生画像，生成默认学习路径。"}],
            }
        
        profile = StudentProfile(**profile_data)
        learning_path, source = await self._generate_path(profile)
        
        path_summary = f"【学习规划】{learning_path.path_name} | 周期: {learning_path.total_weeks}周 | 重点: {', '.join(learning_path.focus_areas)}（来源: {source}）"
        
        return {
            "learning_path": learning_path.model_dump(),
            "messages": [
                {"role": "assistant", "content": path_summary},
            ],
        }
    
    async def _generate_path(self, profile: StudentProfile) -> tuple[LearningPath, str]:
        if self.spark.configured:
            try:
                return await self._generate_with_spark(profile), "spark"
            except Exception as exc:
                logger.warning("星火规划失败，使用规则兜底: %s", exc)
        
        return heuristic_path(profile), "heuristic"
    
    async def _generate_with_spark(self, profile: StudentProfile) -> LearningPath:
        system_prompt = load_planner_prompt()
        profile_json = profile.model_dump_json(exclude={"raw_input"})

        # 明确指示使用画像中的实际学科，不要默认 Python
        subject = _infer_subject(profile)
        goal_label = _get_goal_label(profile.goal)

        user_prompt = (
            f"请根据以下学生画像生成个性化学习路径。\n\n"
            f"【重要】该学生的学习主题是「{subject}」，目标是「{goal_label}」。\n"
            f"学习路径的所有 topics、resources、assessment 都必须围绕「{subject}」来设计，"
            f"不要使用其他学科（如 Python）的内容，除非画像中明确提到。\n\n"
            f"学生画像 JSON：\n{profile_json}\n\n"
            "输出严格 JSON（不要其它说明），字段：\n"
            "path_name, total_weeks, steps(含week,title,duration,topics,resources,assessment), focus_areas, suggestions"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        data = await self.spark.chat_json(messages)
        data["source"] = "spark"
        return LearningPath.model_validate(data)