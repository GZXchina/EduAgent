from __future__ import annotations

import asyncio
from typing import Any

from langgraph.graph import END, StateGraph

from agents.code_agent import CodeAgent
from agents.evaluation_agent import EvaluationAgent
from agents.knowledge_agent import KnowledgeAgent
from agents.mindmap_agent import MindMapAgent
from agents.planner_agent import PlannerAgent
from agents.ppt_agent import PPTAgent
from agents.profile_agent import ProfileAgent
from agents.quiz_agent import QuizAgent
from agents.safety_agent import SafetyAgent
from agents.tutor_agent import TutorAgent
from agents.video_agent import VideoAgent
from workflows.state import AgentState

_profile = ProfileAgent()
_planner = PlannerAgent()
_knowledge = KnowledgeAgent()
_ppt = PPTAgent()
_quiz = QuizAgent()
_code = CodeAgent()
_mindmap = MindMapAgent()
_video = VideoAgent()
_safety = SafetyAgent()
_tutor = TutorAgent()
_evaluation = EvaluationAgent()


async def _node_profile(state: AgentState) -> dict[str, Any]:
    return await _profile.run(dict(state))


async def _node_planner(state: AgentState) -> dict[str, Any]:
    return await _planner.run(dict(state))


async def _node_knowledge(state: AgentState) -> dict[str, Any]:
    return await _knowledge.run(dict(state))


async def _node_resources(state: AgentState) -> dict[str, Any]:
    s = dict(state)
    parts = await asyncio.gather(
        _ppt.run(s),
        _quiz.run(s),
        _code.run(s),
        _mindmap.run(s),
        _video.run(s),
    )

    result: dict[str, Any] = {"messages": []}
    for p in parts:
        result["messages"].extend(p.get("messages", []))
        if "ppt_deck" in p:
            result["ppt_deck"] = p["ppt_deck"]
        if "quiz_set" in p:
            result["quiz_set"] = p["quiz_set"]
        if "code_set" in p:
            result["code_set"] = p["code_set"]
        if "mindmap" in p:
            result["mindmap"] = p["mindmap"]
        if "video_script" in p:
            result["video_script"] = p["video_script"]

    return result


async def _node_safety(state: AgentState) -> dict[str, Any]:
    return await _safety.run(dict(state))


async def _node_tutor(state: AgentState) -> dict[str, Any]:
    return await _tutor.run(dict(state))


async def _node_evaluation(state: AgentState) -> dict[str, Any]:
    return await _evaluation.run(dict(state))


def build_workflow():
    """编排：画像 → 规划 → 知识拆解 → 并行资源生成 → 安全 → 答疑 → 评估。"""
    g: StateGraph[AgentState] = StateGraph(AgentState)
    g.add_node("profile", _node_profile)
    g.add_node("planner", _node_planner)
    g.add_node("knowledge", _node_knowledge)
    g.add_node("resources", _node_resources)
    g.add_node("safety", _node_safety)
    g.add_node("tutor", _node_tutor)
    g.add_node("evaluation", _node_evaluation)

    g.set_entry_point("profile")
    g.add_edge("profile", "planner")
    g.add_edge("planner", "knowledge")
    g.add_edge("knowledge", "resources")
    g.add_edge("resources", "safety")
    g.add_edge("safety", "tutor")
    g.add_edge("tutor", "evaluation")
    g.add_edge("evaluation", END)
    return g.compile()


def default_initial_state(user_input: str, session_id: str | None = None) -> AgentState:
    return {
        "user_input": user_input,
        "session_id": session_id,
        "messages": [{"role": "user", "content": user_input}],
    }