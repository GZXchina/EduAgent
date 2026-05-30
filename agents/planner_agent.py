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


def heuristic_path(profile: StudentProfile) -> LearningPath:
    """星火未配置时的规则兜底学习路径生成。"""
    level = profile.knowledge_level
    goal = profile.goal
    weakness = profile.weakness
    study_time = profile.study_time
    
    base_topics = [
        "Python环境搭建",
        "变量与数据类型",
        "基本输入输出",
        "条件语句",
        "循环结构",
        "函数定义与调用",
        "列表与字典",
        "字符串操作",
        "文件操作",
        "异常处理",
    ]
    
    intermediate_topics = [
        "面向对象编程",
        "模块与包",
        "装饰器",
        "生成器与迭代器",
        "lambda表达式",
        "标准库使用",
        "正则表达式",
        "JSON处理",
    ]
    
    advanced_topics = [
        "算法基础",
        "数据结构",
        "时间复杂度分析",
        "递归",
        "动态规划入门",
        "图论基础",
        "蓝桥杯真题",
        "模拟比赛",
    ]
    
    if "lanqiao" in goal:
        path_name = "蓝桥杯Python竞赛之路"
        focus_areas = ["算法基础", "真题训练", "时间复杂度"]
    elif "postgraduate" in goal:
        path_name = "考研Python复习之路"
        focus_areas = ["数据结构", "算法", "综合应用"]
    elif "job" in goal:
        path_name = "Python就业进阶之路"
        focus_areas = ["项目实战", "框架学习", "面试准备"]
    else:
        path_name = "Python学习之路"
        focus_areas = ["基础知识", "实践应用"]
    
    if weakness:
        focus_areas.append(weakness)
    
    weeks = 8
    if study_time == "unknown":
        weeks = 10
    elif "2h" in study_time:
        weeks = 6
    elif "3h" in study_time:
        weeks = 4
    
    steps = []
    topics_pool = []
    
    if level == "beginner":
        topics_pool = base_topics
        weeks = min(weeks, 10)
    elif level == "intermediate":
        topics_pool = base_topics + intermediate_topics
        weeks = min(weeks, 8)
    else:
        topics_pool = base_topics + intermediate_topics + advanced_topics
        weeks = min(weeks, 6)
    
    topics_per_week = max(1, len(topics_pool) // weeks)
    
    for week in range(1, weeks + 1):
        start_idx = (week - 1) * topics_per_week
        end_idx = start_idx + topics_per_week
        week_topics = topics_pool[start_idx:end_idx]
        
        if week == 1:
            title = "Python基础入门"
            resources = ["图解教程", "视频课程"]
        elif week == weeks:
            title = "综合评估与冲刺"
            resources = ["模拟测试", "真题练习"]
        elif week == weeks - 1:
            title = "专项突破训练"
            resources = ["专项训练", "错题本"]
        else:
            title = f"进阶学习第{week}阶段"
            resources = ["文档教程", "编程练习"]
        
        steps.append(LearningStep(
            week=week,
            title=title,
            duration="7天",
            topics=week_topics or ["复习巩固"],
            resources=resources,
            assessment="编程作业" if week < weeks else "综合测试"
        ))
    
    suggestions = [
        "每天坚持编程练习至少30分钟",
        "建立错题本，定期回顾",
        "完成每个阶段的评估任务",
        "参与社区讨论，交流学习心得"
    ]
    
    if weakness:
        suggestions.insert(0, f"重点攻克薄弱点：{weakness}")
    
    return LearningPath(
        path_name=path_name,
        total_weeks=weeks,
        steps=steps,
        focus_areas=focus_areas,
        suggestions=suggestions,
        source="heuristic"
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
                {"role": "assistant", "content": learning_path.to_markdown()}
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
        
        user_prompt = (
            f"请根据以下学生画像生成个性化学习路径，输出严格 JSON（不要其它说明）：\n\n"
            f"{profile_json}\n\n"
            "JSON 字段：path_name, total_weeks, steps(含week,title,duration,topics,resources,assessment), focus_areas, suggestions"
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        data = await self.spark.chat_json(messages)
        data["source"] = "spark"
        return LearningPath.model_validate(data)