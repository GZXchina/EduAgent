"""多智能体模块（按架构文档拆分，后续接入讯飞星火与 RAG）。"""

from agents.base import BaseAgent
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

__all__ = [
    "BaseAgent",
    "ProfileAgent",
    "PlannerAgent",
    "KnowledgeAgent",
    "PPTAgent",
    "QuizAgent",
    "CodeAgent",
    "MindMapAgent",
    "VideoAgent",
    "TutorAgent",
    "EvaluationAgent",
    "SafetyAgent",
]
