import json
import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from workflows.simple_graph import build_simple_workflow, default_initial_state

logger = logging.getLogger(__name__)
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


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest):
    graph = build_simple_workflow()
    state = default_initial_state(body.message, body.session_id)

    async def event_generator():
        session_id = None
        student_profile = None

        try:
            async for chunk in graph.astream(state):
                for node_name, node_output in chunk.items():
                    node_data = {
                        "type": "node_complete",
                        "node": node_name,
                        "content": "",
                    }

                    msgs = node_output.get("messages", [])
                    if msgs:
                        content_parts = [str(m.get("content", "")) for m in msgs if m.get("role") == "assistant"]
                        if content_parts:
                            node_data["content"] = "\n".join(content_parts)

                    if node_name == "profile":
                        session_id = node_output.get("session_id")
                        student_profile = node_output.get("student_profile")

                    yield f"data: {json.dumps(node_data, ensure_ascii=False)}\n\n"

                    if node_data["content"]:
                        logger.info("[SSE] %s 节点完成，输出 %d 字符", node_name, len(node_data["content"]))

            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'student_profile': student_profile}, ensure_ascii=False)}\n\n"
            logger.info("[SSE] 工作流完成，session_id=%s", session_id)

        except Exception as exc:
            logger.error("[SSE] 工作流异常: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
