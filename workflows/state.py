from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


# 用户意图类型：决定工作流执行路径
INTENT_SIMPLE_QA = "simple_qa"      # 简单问答：只跑 tutor
INTENT_STUDY_PLAN = "study_plan"    # 学习规划：profile + planner + tutor
INTENT_FULL_LEARN = "full_learn"    # 完整学习：全流程


class AgentState(TypedDict, total=False):
    """LangGraph 共享状态（与架构文档一致，可随实现扩展）。"""

    student_profile: dict[str, Any]
    learning_path: dict[str, Any]
    knowledge_tree: dict[str, Any]
    ppt_deck: dict[str, Any]
    quiz_set: dict[str, Any]
    code_set: dict[str, Any]
    mindmap: dict[str, Any]
    video_script: dict[str, Any]
    resource_result: dict[str, Any]
    evaluation_report: dict[str, Any]
    evaluation_suggestions: list[str]
    loop_count: int
    messages: Annotated[list[dict[str, Any]], operator.add]
    session_id: str | None
    user_input: str
    model: str | None  # 用户选择的 AI 模型 ID
    intent: str  # 用户意图：simple_qa / study_plan / full_learn