from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agents.evaluation_agent import EvaluationAgent, generate_evaluation_report
from backend.core.deps import get_db
from database.repository import ProfileRepository, ResourceRepository
from schemas.profile import StudentProfile
from services.evaluation_service import (
    EvaluationService,
    LearningBehaviorData,
    get_evaluation_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evaluation", tags=["evaluation"])

_evaluation_service: EvaluationService | None = None
_evaluation_agent: EvaluationAgent | None = None


def get_service() -> EvaluationService:
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = get_evaluation_service()
    return _evaluation_service


def get_agent() -> EvaluationAgent:
    global _evaluation_agent
    if _evaluation_agent is None:
        _evaluation_agent = EvaluationAgent()
    return _evaluation_agent


class LearningBehaviorRequest(BaseModel):
    """学习行为数据请求。"""

    study_duration_minutes: int = Field(default=0, description="学习时长(分钟)")
    quiz_results: list[dict[str, Any]] = Field(default_factory=list, description="练习结果列表")
    knowledge_mastery: dict[str, float] = Field(default_factory=dict, description="知识掌握度")
    resource_usage: dict[str, int] = Field(default_factory=dict, description="资源使用次数")


class EvaluationRequest(BaseModel):
    """学习评估请求。"""

    student_profile: dict[str, Any] = Field(description="学生画像数据")
    learning_behavior: LearningBehaviorRequest = Field(description="学习行为数据")


class EvaluationResponse(BaseModel):
    """学习评估响应。"""

    score: int = Field(description="综合评分(0-100)")
    level: str = Field(description="等级(优秀/良好/中等/需加强)")
    comment: str = Field(description="总体评价")
    analysis: dict[str, Any] = Field(description="各维度分析")
    strengths: list[str] = Field(description="优势列表")
    weaknesses: list[str] = Field(description="薄弱点列表")
    suggestions: list[str] = Field(description="建议列表")
    evaluated: bool = Field(default=True, description="评估完成标记")


@router.post("/report", response_model=EvaluationResponse)
async def evaluate_learning(request: EvaluationRequest) -> EvaluationResponse:
    """生成学习评估报告。"""
    try:
        service = get_service()
        behavior_data = LearningBehaviorData.from_dict(request.learning_behavior.model_dump())
        profile_data = request.student_profile
        profile = StudentProfile(**profile_data)

        report = service.generate_report(profile, behavior_data)
        return EvaluationResponse(**report)

    except Exception as exc:
        logger.error("评估失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"评估失败: {exc}")


@router.post("/behavior")
async def submit_learning_behavior(behavior: LearningBehaviorRequest) -> dict[str, Any]:
    """提交学习行为数据。"""
    try:
        service = get_service()
        behavior_data = LearningBehaviorData.from_dict(behavior.model_dump())
        analysis = service.analyze_behavior(behavior_data)
        return {
            "success": True,
            "message": "学习行为数据已记录",
            "analysis": analysis,
        }
    except Exception as exc:
        logger.error("提交学习行为失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"提交失败: {exc}")


@router.get("/metrics")
async def get_evaluation_metrics() -> dict[str, str]:
    """获取评估指标说明。"""
    return {
        "quiz_accuracy": "练习正确率(%)",
        "knowledge_mastery_score": "知识掌握度得分(%)",
        "resource_utilization": "资源利用率(%)",
        "dedication_score": "学习投入度得分(%)",
    }


@router.post("/profile-update")
async def update_profile_from_evaluation(
    student_profile: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    """根据评估报告更新学生画像。"""
    try:
        service = get_service()
        profile = StudentProfile(**student_profile)
        updated = service.update_profile_from_report(profile, report)
        return {
            "success": True,
            "updated_profile": updated,
        }
    except Exception as exc:
        logger.error("更新画像失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"更新失败: {exc}")


class LLMEvaluationRequest(BaseModel):
    """LLM驱动的评估请求。"""

    student_profile: dict[str, Any] = Field(description="学生画像数据")
    resource_usage: dict[str, Any] = Field(default_factory=dict, description="资源使用情况")
    session_id: str | None = Field(default=None, description="会话ID")


class LLMEvaluationResponse(BaseModel):
    """LLM评估响应。"""

    score: int = Field(description="综合评分(0-100)")
    level: str = Field(description="等级")
    comment: str = Field(description="总体评价")
    strengths: list[str] = Field(description="优势列表")
    weaknesses: list[str] = Field(description="薄弱点列表")
    suggestions: list[str] = Field(description="建议列表")
    evaluated: bool = Field(default=True)
    source: str = Field(default="heuristic", description="评估来源: spark / heuristic")


@router.post("/llm-report", response_model=LLMEvaluationResponse)
async def evaluate_with_llm(request: LLMEvaluationRequest) -> LLMEvaluationResponse:
    """使用LLM大模型驱动生成学习评估报告。"""
    try:
        agent = get_agent()
        profile = StudentProfile(**request.student_profile) if request.student_profile else StudentProfile()

        resource_usage = request.resource_usage or {
            "ppt_deck": {},
            "quiz_set": {},
            "code_set": {},
            "mindmap": {},
            "video_script": {},
        }

        report = await agent._generate_evaluation(profile, resource_usage)

        if request.session_id:
            db = next(get_db())
            try:
                repo = ResourceRepository(db)
                score_val = float(report["score"])
                repo.save_evaluation_report(request.session_id, report, score=score_val)
            except Exception as exc:
                logger.warning("保存LLM评估报告失败: %s", exc)
            finally:
                db.close()

        return LLMEvaluationResponse(**report)

    except Exception as exc:
        logger.error("LLM评估失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"LLM评估失败: {exc}")


class HistoryReportItem(BaseModel):
    """历史评估报告条目。"""

    id: int
    score: float | None
    report: dict[str, Any]
    created_at: str


class EvaluationHistoryResponse(BaseModel):
    """评估历史响应。"""

    session_id: str
    reports: list[HistoryReportItem]
    total: int
    average_score: float | None
    trend: str = Field(default="stable", description="趋势: improving / declining / stable")


@router.get("/history/{session_id}", response_model=EvaluationHistoryResponse)
async def get_evaluation_history(
    session_id: str,
    db: Session = Depends(get_db),
) -> EvaluationHistoryResponse:
    """获取指定会话的历史评估报告。"""
    try:
        repo = ResourceRepository(db)
        report_rows = repo.get_evaluation_reports(session_id)

        reports: list[HistoryReportItem] = []
        scores: list[float] = []

        for row in report_rows:
            report_dict = ResourceRepository.report_to_dict(row)
            reports.append(HistoryReportItem(
                id=row.id,
                score=row.score,
                report=report_dict,
                created_at=row.created_at.isoformat() if row.created_at else "",
            ))
            if row.score is not None:
                scores.append(row.score)

        trend = "stable"
        if len(scores) >= 2:
            if scores[0] > scores[-1]:
                trend = "improving"
            elif scores[0] < scores[-1]:
                trend = "declining"

        return EvaluationHistoryResponse(
            session_id=session_id,
            reports=reports,
            total=len(reports),
            average_score=round(sum(scores) / len(scores), 1) if scores else None,
            trend=trend,
        )

    except Exception as exc:
        logger.error("获取评估历史失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"获取历史失败: {exc}")


class SessionMetricsResponse(BaseModel):
    """会话级行为指标响应。"""

    session_id: str
    has_profile: bool
    has_resources: bool
    resource_types: list[str]
    resource_count: int
    evaluation_count: int
    latest_evaluation: dict[str, Any] | None


@router.get("/session-metrics/{session_id}", response_model=SessionMetricsResponse)
async def get_session_metrics(
    session_id: str,
    db: Session = Depends(get_db),
) -> SessionMetricsResponse:
    """获取会话级自动追踪的学习行为指标。"""
    try:
        profile_repo = ProfileRepository(db)
        resource_repo = ResourceRepository(db)

        profile_row = profile_repo.get_by_session(session_id)
        resource_rows = resource_repo.get_resources_by_session(session_id)
        report_rows = resource_repo.get_evaluation_reports(session_id)

        resource_types = list({r.resource_type for r in resource_rows})
        latest_eval = None
        if report_rows:
            latest = report_rows[0]
            latest_eval = ResourceRepository.report_to_dict(latest)

        return SessionMetricsResponse(
            session_id=session_id,
            has_profile=profile_row is not None,
            has_resources=len(resource_rows) > 0,
            resource_types=resource_types,
            resource_count=len(resource_rows),
            evaluation_count=len(report_rows),
            latest_evaluation=latest_eval,
        )

    except Exception as exc:
        logger.error("获取会话指标失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"获取指标失败: {exc}")


class BehaviorTrackingRequest(BaseModel):
    """行为追踪请求。"""

    session_id: str = Field(description="会话ID")
    action: str = Field(description="行为动作: chat / quiz / resource_view / resource_download")
    detail: dict[str, Any] = Field(default_factory=dict, description="行为详情")
    duration_minutes: int = Field(default=0, description="本次行为时长(分钟)")


@router.post("/track-behavior")
async def track_learning_behavior(
    request: BehaviorTrackingRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """追踪并记录学习行为。"""
    try:
        logger.info(
            "行为追踪: session=%s action=%s duration=%dmin",
            request.session_id,
            request.action,
            request.duration_minutes,
        )

        return {
            "success": True,
            "message": f"行为 '{request.action}' 已记录",
            "session_id": request.session_id,
            "tracked_at": __import__("datetime").datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.error("行为追踪失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"追踪失败: {exc}")