from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from workflows.simple_graph import build_simple_workflow, default_initial_state

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户自然语言输入")
    session_id: str | None = Field(default=None, description="可选会话标识")


class ChatResponse(BaseModel):
    reply: str
    session_id: str | None = None
    student_profile: dict[str, Any] | None = None
    state: dict[str, Any]


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    graph = build_simple_workflow()
    state = default_initial_state(body.message, body.session_id)
    result = await graph.ainvoke(state)
    msgs = list(result.get("messages") or [])
    assistant_lines = [str(m.get("content", "")) for m in msgs if m.get("role") == "assistant"]
    reply = "\n".join(assistant_lines) if assistant_lines else "工作流已执行。"
    return ChatResponse(
        reply=reply,
        session_id=result.get("session_id"),
        student_profile=result.get("student_profile"),
        state=dict(result),
    )
