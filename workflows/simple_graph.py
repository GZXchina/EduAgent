"""简化版工作流：跳过资源生成阶段，只包含核心功能。"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from agents.profile_agent import ProfileAgent
from agents.planner_agent import PlannerAgent
from agents.knowledge_agent import KnowledgeAgent
from agents.tutor_agent import TutorAgent
from workflows.state import AgentState

_profile = ProfileAgent()
_planner = PlannerAgent()
_knowledge = KnowledgeAgent()
_tutor = TutorAgent()


async def _node_profile(state: AgentState) -> dict[str, Any]:
    return await _profile.run(dict(state))


async def _node_planner(state: AgentState) -> dict[str, Any]:
    return await _planner.run(dict(state))


async def _node_knowledge(state: AgentState) -> dict[str, Any]:
    return await _knowledge.run(dict(state))


async def _node_tutor(state: AgentState) -> dict[str, Any]:
    return await _tutor.run(dict(state))


def build_simple_workflow():
    """简化编排：画像 → 规划 → 知识拆解 → 答疑。"""
    g: StateGraph[AgentState] = StateGraph(AgentState)
    g.add_node("profile", _node_profile)
    g.add_node("planner", _node_planner)
    g.add_node("knowledge", _node_knowledge)
    g.add_node("tutor", _node_tutor)

    g.set_entry_point("profile")
    g.add_edge("profile", "planner")
    g.add_edge("planner", "knowledge")
    g.add_edge("knowledge", "tutor")
    g.add_edge("tutor", END)
    return g.compile()


def default_initial_state(user_input: str, session_id: str | None = None) -> AgentState:
    return {
        "user_input": user_input,
        "session_id": session_id,
        "messages": [{"role": "user", "content": user_input}],
    }
