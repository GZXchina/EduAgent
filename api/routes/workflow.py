from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.deps import get_db
from database.repository import ProfileRepository, ResourceRepository
from workflows.graph import build_workflow, default_initial_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class WorkflowExecuteRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户自然语言输入")
    session_id: str | None = Field(default=None, description="可选会话标识，为空时自动生成")


class WorkflowExecuteResponse(BaseModel):
    session_id: str
    student_profile: dict[str, Any] | None = None
    learning_path: dict[str, Any] | None = None
    knowledge_tree: dict[str, Any] | None = None
    ppt_deck: dict[str, Any] | None = None
    quiz_set: dict[str, Any] | None = None
    code_set: dict[str, Any] | None = None
    mindmap: dict[str, Any] | None = None
    video_script: dict[str, Any] | None = None
    evaluation_report: dict[str, Any] | None = None
    messages: list[dict[str, Any]] = []


class WorkflowStatusResponse(BaseModel):
    session_id: str
    student_profile: dict[str, Any] | None = None
    resources: list[dict[str, Any]] = []
    evaluation_reports: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# POST /api/workflow/execute
# ---------------------------------------------------------------------------

@router.post("/execute", response_model=WorkflowExecuteResponse)
async def execute_workflow(body: WorkflowExecuteRequest) -> WorkflowExecuteResponse:
    session_id = body.session_id or uuid.uuid4().hex

    graph = build_workflow()
    state = default_initial_state(body.message, session_id)

    try:
        result = await graph.ainvoke(state)
    except Exception as exc:
        logger.exception("完整工作流执行失败 session_id=%s", session_id)
        raise HTTPException(status_code=500, detail=f"工作流执行失败: {exc}") from exc

    return WorkflowExecuteResponse(
        session_id=result.get("session_id", session_id),
        student_profile=result.get("student_profile"),
        learning_path=result.get("learning_path"),
        knowledge_tree=result.get("knowledge_tree"),
        ppt_deck=result.get("ppt_deck"),
        quiz_set=result.get("quiz_set"),
        code_set=result.get("code_set"),
        mindmap=result.get("mindmap"),
        video_script=result.get("video_script"),
        evaluation_report=result.get("evaluation_report"),
        messages=result.get("messages", []),
    )


# ---------------------------------------------------------------------------
# GET /api/workflow/status/{session_id}
# ---------------------------------------------------------------------------

@router.get("/status/{session_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    session_id: str,
    db: Session = Depends(get_db),
) -> WorkflowStatusResponse:
    repo = ResourceRepository(db)

    # 查询学习资源
    resource_rows = repo.get_resources_by_session(session_id)
    resources = [
        {
            "id": row.id,
            "resource_type": row.resource_type,
            "content": ResourceRepository.resource_to_dict(row),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in resource_rows
    ]

    # 查询评估报告
    report_rows = repo.get_evaluation_reports(session_id)
    evaluation_reports = [ResourceRepository.report_to_dict(row) for row in report_rows]

    # 查询学生画像
    profile_repo = ProfileRepository(db)
    profile_row = profile_repo.get_by_session(session_id)
    student_profile = ProfileRepository.to_dict(profile_row) if profile_row else None

    return WorkflowStatusResponse(
        session_id=session_id,
        student_profile=student_profile,
        resources=resources,
        evaluation_reports=evaluation_reports,
    )
