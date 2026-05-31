from __future__ import annotations

import asyncio
import logging
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
from database.repository import ResourceRepository
from database.session import SessionLocal
from workflows.state import AgentState

logger = logging.getLogger(__name__)

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


def _persist_resources(session_id: str | None, result: dict[str, Any]) -> None:
    if session_id is None:
        return
    db = SessionLocal()
    try:
        repo = ResourceRepository(db)
        resource_types = {
            "ppt_deck": "ppt",
            "quiz_set": "quiz",
            "code_set": "code",
            "mindmap": "mindmap",
            "video_script": "video",
        }
        for key, rtype in resource_types.items():
            if key in result:
                repo.save_resource(session_id, rtype, result[key])
    except Exception as exc:
        logger.warning("保存学习资源失败: %s", exc)
    finally:
        db.close()


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

    await asyncio.to_thread(_persist_resources, state.get("session_id"), result)
    return result


async def _node_safety(state: AgentState) -> dict[str, Any]:
    return await _safety.run(dict(state))


async def _node_tutor(state: AgentState) -> dict[str, Any]:
    return await _tutor.run(dict(state))


def _persist_evaluation(session_id: str | None, report: dict[str, Any]) -> None:
    if session_id is None:
        return
    db = SessionLocal()
    try:
        repo = ResourceRepository(db)
        score = report.get("score")
        if isinstance(score, int):
            score = float(score)
        repo.save_evaluation_report(session_id, report, score=score)
    except Exception as exc:
        logger.warning("保存评估报告失败: %s", exc)
    finally:
        db.close()


async def _node_evaluation(state: AgentState) -> dict[str, Any]:
    result = await _evaluation.run(dict(state))
    if result.get("evaluation_report"):
        await asyncio.to_thread(
            _persist_evaluation,
            state.get("session_id"),
            result["evaluation_report"],
        )
    return result


def _evaluation_router(state: AgentState) -> str:
    """根据评估分数和循环次数决定是回流还是结束。

    - score < 60 且 loop_count < 2 → 回流到 profile 重新生成
    - 否则 → 结束
    """
    report = state.get("evaluation_report", {})
    score = report.get("score", 0) if isinstance(report, dict) else 0
    loop_count = state.get("loop_count", 0)

    if score < 60 and loop_count < 2:
        logger.info(
            "评估分数 %.0f 低于阈值，第 %d 次回流至 profile",
            score,
            loop_count + 1,
        )
        return "loop"
    return "end"


async def _node_loop_back(state: AgentState) -> dict[str, Any]:
    """回流节点：递增 loop_count 并将评估建议注入 state，供 ProfileAgent 参考。"""
    report = state.get("evaluation_report", {})
    suggestions = report.get("suggestions", []) if isinstance(report, dict) else []
    loop_count = state.get("loop_count", 0)

    logger.info(
        "回流机制触发（第 %d 次），注入 %d 条评估建议",
        loop_count + 1,
        len(suggestions),
    )

    return {
        "loop_count": loop_count + 1,
        "evaluation_suggestions": suggestions,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"[回流调整] 根据评估建议调整学习路径："
                    + (", ".join(suggestions)
                        if suggestions
                        else "无具体建议"
                    )
                ),
            }
        ],
    }


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
    g.add_node("loop_back", _node_loop_back)

    g.set_entry_point("profile")
    g.add_edge("profile", "planner")
    g.add_edge("planner", "knowledge")
    g.add_edge("knowledge", "resources")
    g.add_edge("resources", "safety")
    g.add_edge("safety", "tutor")
    g.add_edge("tutor", "evaluation")
    g.add_conditional_edges(
        "evaluation",
        _evaluation_router,
        {"loop": "loop_back", "end": END},
    )
    g.add_edge("loop_back", "profile")
    return g.compile()


def default_initial_state(user_input: str, session_id: str | None = None) -> AgentState:
    return {
        "user_input": user_input,
        "session_id": session_id,
        "loop_count": 0,
        "messages": [{"role": "user", "content": user_input}],
    }