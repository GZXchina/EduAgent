from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from schemas.profile import StudentProfile
from services.evaluation_service import (
    EvaluationService,
    LearningBehaviorData,
    get_evaluation_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evaluation", tags=["evaluation"])

_evaluation_service: EvaluationService | None = None


def get_service() -> EvaluationService:
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = get_evaluation_service()
    return _evaluation_service


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