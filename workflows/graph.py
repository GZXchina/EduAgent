from __future__ import annotations

import asyncio
import logging
import re
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
from workflows.state import (
    AgentState,
    INTENT_SIMPLE_QA,
    INTENT_STUDY_PLAN,
    INTENT_FULL_LEARN,
)

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


# ========== 智能路由：分析问题类型决定执行路径 ==========

# 简单问答关键词：只跑 tutor，快速响应
_SIMPLE_QA_PATTERNS = [
    r"是什么[？?。.]?$",
    r"是什么意思",
    r"怎么[用写做搞]",
    r"如何[使用实现]",
    r"解释[一下]?[下]?[这那个]",
    r"举例",
    r"区别",
    r"对比",
    r"为什么",
    r"什么[时候时]候",
    r"哪里[错了]",
    r"报错",
    r"错误",
    r"异常",
    r"bug",
]

# 学习规划关键词：profile + planner + tutor
_STUDY_PLAN_PATTERNS = [
    r"学习[路线规划计划计划安排]",
    r"怎么学",
    r"如何学",
    r"帮我[规划安排制定]",
    r"我想学",
    r"从零[开零]学",
    r"入门",
    r"新手[怎么如何]",
    r"基础[知识教程]",
    r"进阶[教程路线]",
    r"提升[能力水平]",
    r"准备[面试考试]",
    r"准备.*比赛",
    r"求职",
    r"面试",
]

# 完整学习关键词：全流程（生成PPT/测验/代码等）
_FULL_LEARN_PATTERNS = [
    r"系统学习",
    r"完整[教程课程]",
    r"全套[资源教程课程]",
    r"生成[课程资源]",
    r"制作[PPT课件]",
    r"出.{0,3}[道]",
    r"练习[题]",
    r"测验",
    r"考试[题]",
    r"思维导图",
    r"知识[图谱框架]",
]


def _classify_intent(user_input: str) -> str:
    """根据用户输入分类意图类型。

    优先级：full_learn > study_plan > simple_qa
    """
    text = user_input.lower().strip()

    # 检查完整学习模式
    for pattern in _FULL_LEARN_PATTERNS:
        if re.search(pattern, text):
            return INTENT_FULL_LEARN

    # 检查学习规划模式
    for pattern in _STUDY_PLAN_PATTERNS:
        if re.search(pattern, text):
            return INTENT_STUDY_PLAN

    # 检查简单问答模式
    for pattern in _SIMPLE_QA_PATTERNS:
        if re.search(pattern, text):
            return INTENT_SIMPLE_QA

    # 默认：简单问答（快速响应）
    return INTENT_SIMPLE_QA


async def _node_router(state: AgentState) -> dict[str, Any]:
    """路由节点：分析用户问题类型，决定执行路径。"""
    user_input = state.get("user_input", "")
    intent = _classify_intent(user_input)

    intent_labels = {
        INTENT_SIMPLE_QA: "快速问答",
        INTENT_STUDY_PLAN: "学习规划",
        INTENT_FULL_LEARN: "完整学习",
    }

    logger.info(
        "智能路由: input='%s' → intent=%s (%s)",
        user_input[:50],
        intent,
        intent_labels.get(intent, "未知"),
    )

    return {
        "intent": intent,
        "messages": [],
    }


def _route_after_router(state: AgentState) -> str:
    """根据意图决定下一个节点。"""
    intent = state.get("intent", INTENT_SIMPLE_QA)

    if intent == INTENT_FULL_LEARN:
        return "profile"  # 全流程
    elif intent == INTENT_STUDY_PLAN:
        return "profile"  # 画像+规划
    else:
        return "tutor"  # 直接问答


def _route_after_profile(state: AgentState) -> str:
    """根据意图决定 profile 之后的节点。"""
    intent = state.get("intent", INTENT_SIMPLE_QA)

    if intent == INTENT_FULL_LEARN:
        return "planner"  # 全流程继续
    else:
        return "tutor"  # 学习规划完成后直接回答


def _route_after_planner(state: AgentState) -> str:
    """根据意图决定 planner 之后的节点。"""
    intent = state.get("intent", INTENT_SIMPLE_QA)

    if intent == INTENT_FULL_LEARN:
        return "knowledge"  # 全流程继续
    else:
        return "tutor"  # 规划完成后直接回答


# ========== 工作流节点 ==========


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
    """智能路由工作流：根据问题类型决定执行路径。

    执行路径：
    - simple_qa（简单问答）: router → tutor → evaluation → END
    - study_plan（学习规划）: router → profile → tutor → evaluation → END
    - full_learn（完整学习）: router → profile → planner → knowledge → resources → safety → tutor → evaluation → END
    """
    g: StateGraph[AgentState] = StateGraph(AgentState)

    # 添加所有节点
    g.add_node("router", _node_router)
    g.add_node("profile", _node_profile)
    g.add_node("planner", _node_planner)
    g.add_node("knowledge", _node_knowledge)
    g.add_node("resources", _node_resources)
    g.add_node("safety", _node_safety)
    g.add_node("tutor", _node_tutor)
    g.add_node("evaluation", _node_evaluation)
    g.add_node("loop_back", _node_loop_back)

    # 入口点：路由节点
    g.set_entry_point("router")

    # 路由节点 → 根据意图跳转
    g.add_conditional_edges(
        "router",
        _route_after_router,
        {"profile": "profile", "tutor": "tutor"},
    )

    # profile 节点 → 根据意图跳转
    g.add_conditional_edges(
        "profile",
        _route_after_profile,
        {"planner": "planner", "tutor": "tutor"},
    )

    # planner 节点 → 根据意图跳转
    g.add_conditional_edges(
        "planner",
        _route_after_planner,
        {"knowledge": "knowledge", "tutor": "tutor"},
    )

    # 完整学习路径（固定边）
    g.add_edge("knowledge", "resources")
    g.add_edge("resources", "safety")
    g.add_edge("safety", "tutor")

    # tutor → evaluation（所有路径都经过评估）
    g.add_edge("tutor", "evaluation")

    # evaluation → 根据分数决定是否回流
    g.add_conditional_edges(
        "evaluation",
        _evaluation_router,
        {"loop": "loop_back", "end": END},
    )

    # 回流到 profile
    g.add_edge("loop_back", "profile")

    return g.compile()


def default_initial_state(
    user_input: str,
    session_id: str | None = None,
    history: list[dict[str, str]] | None = None,
    model: str | None = None,
) -> AgentState:
    messages: list[dict[str, Any]] = []
    # 注入对话历史，使多轮对话上下文可用
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_input})
    return {
        "user_input": user_input,
        "session_id": session_id,
        "loop_count": 0,
        "messages": messages,
        "model": model,
    }