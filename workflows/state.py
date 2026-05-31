from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


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