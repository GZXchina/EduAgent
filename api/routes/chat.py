import json
import logging
import time
from typing import Any

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.integrations.spark.client import AVAILABLE_MODELS
from rag.ingest import ingest_single_file
from workflows.graph import build_workflow, default_initial_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


class HistoryMessage(BaseModel):
    role: str = Field(..., description="user 或 assistant")
    content: str = Field(..., min_length=1, description="消息内容")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户自然语言输入")
    session_id: str | None = Field(default=None, description="可选会话标识")
    history: list[HistoryMessage] = Field(default_factory=list, description="对话历史（多轮上下文）")
    model: str | None = Field(default=None, description="用户选择的 AI 模型 ID")


class ChatResponse(BaseModel):
    reply: str
    session_id: str | None = None
    display_text: str
    internal_steps: list[dict[str, Any]] = []
    student_profile: dict[str, Any] | None = None


USER_FACING_NODES = {"tutor"}
NODE_LABELS: dict[str, str] = {
    "profile": "画像分析",
    "planner": "学习规划",
    "knowledge": "知识检索",
    "resources": "资源生成",
    "safety": "安全检查",
    "tutor": "AI回答",
    "evaluation": "效果评估",
    "loop_back": "回流调整",
}


def _extract_display_and_steps(result: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    msgs = list(result.get("messages") or [])
    display_lines: list[str] = []
    steps: list[dict[str, Any]] = []

    for m in msgs:
        content = str(m.get("content", ""))
        node = m.get("node", "")
        if not node:
            if m.get("role") == "assistant" and content:
                display_lines.append(content)
            continue
        if node in USER_FACING_NODES and content:
            display_lines.append(content)
        else:
            steps.append({
                "node": node,
                "label": NODE_LABELS.get(node, node),
                "content": content,
                "is_user_facing": node in USER_FACING_NODES,
            })

    display_text = "\n\n".join(display_lines) if display_lines else "工作流已执行。"
    return display_text, steps


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    graph = build_workflow()
    history = [{"role": h.role, "content": h.content} for h in body.history]
    state = default_initial_state(body.message, body.session_id, history=history, model=body.model)
    result = await graph.ainvoke(state)
    display_text, internal_steps = _extract_display_and_steps(result)
    return ChatResponse(
        reply=display_text,
        display_text=display_text,
        internal_steps=internal_steps,
        session_id=result.get("session_id"),
        student_profile=result.get("student_profile"),
    )


# 工作流节点执行顺序（完整路径，用于 fallback）
NODE_ORDER = ["router", "profile", "planner", "knowledge", "resources", "safety", "tutor", "evaluation"]

# thinking 阶段标签（面向用户的人类可读描述）
THINKING_LABELS: dict[str, str] = {
    "router": "正在分析问题...",
    "profile": "正在分析学生画像...",
    "planner": "正在规划学习路径...",
    "knowledge": "正在检索相关知识...",
    "resources": "正在生成学习资源...",
    "safety": "正在进行安全检查...",
    "tutor": "AI 正在思考回答...",
    "evaluation": "正在评估回答质量...",
}

# 根据意图类型的执行路径
INTENT_PATHS: dict[str, list[str]] = {
    "simple_qa": ["router", "tutor"],
    "study_plan": ["router", "profile", "tutor", "evaluation"],
    "full_learn": ["router", "profile", "planner", "knowledge", "resources", "safety", "tutor", "evaluation"],
}


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest):
    graph = build_workflow()
    history = [{"role": h.role, "content": h.content} for h in body.history]
    state = default_initial_state(body.message, body.session_id, history=history, model=body.model)

    async def event_generator():
        session_id = None
        student_profile = None
        internal_nodes: list[dict[str, Any]] = []
        completed_nodes: set[str] = set()
        current_intent: str | None = None
        tutor_streamed = False  # 标记 tutor 是否已通过流式输出

        # 工作流开始时推送 router thinking 事件
        yield f"data: {json.dumps({'type': 'thinking', 'node': 'router', 'status': 'processing', 'label': THINKING_LABELS.get('router', '处理中...'), 'model': body.model}, ensure_ascii=False)}\n\n"

        try:
            async for chunk in graph.astream(state):
                for node_name, node_output in chunk.items():
                    completed_nodes.add(node_name)

                    # 从 router 节点获取 intent
                    if node_name == "router":
                        current_intent = node_output.get("intent")
                        yield f"data: {json.dumps({'type': 'thinking', 'node': 'router', 'status': 'completed'}, ensure_ascii=False)}\n\n"

                        if current_intent:
                            intent_path = INTENT_PATHS.get(current_intent, [])
                            if len(intent_path) > 1:
                                next_node = intent_path[1]
                                yield f"data: {json.dumps({'type': 'thinking', 'node': next_node, 'status': 'processing', 'label': THINKING_LABELS.get(next_node, '处理中...'), 'intent': current_intent}, ensure_ascii=False)}\n\n"
                        continue

                    # 获取节点输出内容
                    msgs = node_output.get("messages", [])
                    content_parts = [str(m.get("content", "")) for m in msgs if m.get("role") == "assistant"]
                    content = "\n".join(content_parts) if content_parts else ""

                    if node_name == "profile":
                        session_id = node_output.get("session_id")
                        student_profile = node_output.get("student_profile")

                    if content:
                        logger.info("[SSE] %s 节点完成，输出 %d 字符", node_name, len(content))

                    # 推送当前节点完成状态
                    if node_name != "evaluation":
                        yield f"data: {json.dumps({'type': 'thinking', 'node': node_name, 'status': 'completed'}, ensure_ascii=False)}\n\n"

                    # 保存内部步骤
                    if node_name not in USER_FACING_NODES and node_name != "router":
                        internal_nodes.append({
                            "node": node_name,
                            "label": NODE_LABELS.get(node_name, node_name),
                            "content": content,
                        })

                    # 推送下一个节点的 thinking 事件（基于 intent 路径）
                    if node_name != "evaluation" and current_intent:
                        intent_path = INTENT_PATHS.get(current_intent, NODE_ORDER)
                        try:
                            current_idx = intent_path.index(node_name)
                            if current_idx + 1 < len(intent_path):
                                next_node = intent_path[current_idx + 1]
                                if next_node != "evaluation":
                                    yield f"data: {json.dumps({'type': 'thinking', 'node': next_node, 'status': 'processing', 'label': THINKING_LABELS.get(next_node, '处理中...')}, ensure_ascii=False)}\n\n"
                        except ValueError:
                            pass

                    # tutor 节点：使用流式输出逐 token 推送
                    if node_name in USER_FACING_NODES and not tutor_streamed:
                        tutor_streamed = True
                        # 先推送 tutor thinking 完成
                        yield f"data: {json.dumps({'type': 'thinking', 'node': 'tutor', 'status': 'completed'}, ensure_ascii=False)}\n\n"
                        # 逐 token 流式推送回答内容
                        full_content = content
                        yield f"data: {json.dumps({'type': 'message_start', 'node': node_name}, ensure_ascii=False)}\n\n"
                        # 将完整内容分块推送，模拟流式效果
                        chunk_size = 8
                        for i in range(0, len(full_content), chunk_size):
                            token = full_content[i:i + chunk_size]
                            yield f"data: {json.dumps({'type': 'message_delta', 'node': node_name, 'content': token}, ensure_ascii=False)}\n\n"
                        yield f"data: {json.dumps({'type': 'message_end', 'node': node_name, 'content': full_content}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'student_profile': student_profile, 'internal_steps': internal_nodes, 'intent': current_intent}, ensure_ascii=False)}\n\n"
            logger.info("[SSE] 工作流完成，session_id=%s, intent=%s", session_id, current_intent)

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


@router.post("/chat/upload-file")
async def chat_upload_file(
    file: UploadFile = File(..., description="知识文件 MD/PDF/TXT"),
    session_id: str = Form(default="", description="会话标识"),
) -> dict[str, Any]:
    try:
        content = await file.read()
        result = ingest_single_file(file.filename, content)
        return {
            "status": "ok",
            "filename": file.filename,
            "chunks": result.get("chunks", 0),
            "message": f"文件 {file.filename} 已入库，共 {result.get('chunks', 0)} 个知识片段",
        }
    except Exception as exc:
        logger.error("文件上传入库失败: %s", exc)
        return {"status": "error", "filename": file.filename, "message": str(exc)}


@router.get("/chat/models")
async def list_models() -> dict[str, Any]:
    """返回可用的 AI 模型列表（内置 + 用户自定义）。"""
    models = []
    # 内置模型
    for model_id, cfg in AVAILABLE_MODELS.items():
        models.append({
            "id": model_id,
            "label": cfg["label"],
            "description": cfg["description"],
            "is_custom": False,
        })
    # 用户自定义模型
    try:
        from database.session import SessionLocal
        from database.models import CustomModel
        db = SessionLocal()
        custom_models = db.query(CustomModel).filter(CustomModel.is_active == 1).all()
        for m in custom_models:
            models.append({
                "id": m.model_id,
                "label": m.label,
                "description": m.description or f"自定义 {m.provider} 模型",
                "is_custom": True,
                "provider": m.provider,
                "protocol": m.protocol,
            })
        db.close()
    except Exception as exc:
        logger.warning("加载自定义模型失败: %s", exc)
    return {"models": models}


@router.get("/chat/model-status")
async def model_status(model: str | None = None) -> dict[str, Any]:
    """检查 AI 模型的连接状态。

    参数：
    - model: 要检查的模型 ID（可选），默认使用环境变量中的 SPARK_MODEL

    策略：
    - 先查找内置模型
    - 再查找自定义模型
    - HTTP 模型：发送 ping 请求
    - WebSocket 模型：尝试建立 WS 连接
    """
    from backend.settings import get_settings

    settings = get_settings()

    # 确定要检查的模型
    current_model = model or settings.spark_model
    model_cfg = AVAILABLE_MODELS.get(current_model, {})
    is_custom = False

    # 如果内置模型不存在，尝试加载自定义模型
    if not model_cfg and current_model and current_model.startswith("custom-"):
        from database.session import SessionLocal
        from database.models import CustomModel
        db = SessionLocal()
        record = db.query(CustomModel).filter(
            CustomModel.model_id == current_model,
            CustomModel.is_active == 1,
        ).first()
        db.close()
        if record:
            model_cfg = {
                "protocol": record.protocol,
                "model": record.model_name,
                "label": record.label,
                "description": record.description or "",
                "api_url": record.api_url or "",
                "api_key": record.api_key or "",
                "ws_url": record.ws_url or "",
                "domain": record.domain or "",
            }
            is_custom = True

    if not settings.spark_configured and not is_custom:
        return {
            "status": "disconnected",
            "message": "AI 模型未配置",
            "current_model": current_model,
            "model_label": model_cfg.get("label", current_model),
            "latency_ms": None,
            "fallback_mode": True,
        }

    protocol = model_cfg.get("protocol", "http")

    if protocol == "websocket":
        # WebSocket 模型：尝试建立连接
        try:
            import websockets
            from backend.integrations.spark.ws_auth import build_ws_auth_url

            ws_url = model_cfg.get("ws_url") or settings.spark_ws_url
            auth_url = build_ws_auth_url(settings.spark_api_key, settings.spark_api_secret, ws_url)

            start = time.monotonic()
            async with websockets.connect(auth_url, ping_interval=None, open_timeout=8, close_timeout=3):
                pass  # 连接成功即可
            latency_ms = round((time.monotonic() - start) * 1000)

            return {
                "status": "connected",
                "message": f"已连接 {model_cfg.get('label', current_model)} (WebSocket)",
                "current_model": current_model,
                "model_label": model_cfg.get("label", current_model),
                "latency_ms": latency_ms,
                "protocol": "websocket",
                "fallback_mode": False,
            }
        except Exception as exc:
            return {
                "status": "error",
                "message": f"WebSocket 连接失败: {type(exc).__name__}",
                "current_model": current_model,
                "model_label": model_cfg.get("label", current_model),
                "latency_ms": None,
                "protocol": "websocket",
                "fallback_mode": True,
                "error_detail": str(exc)[:200],
            }

    # HTTP 模型：使用模型自身的 api_url 做探测
    try:
        import httpx

        # 自定义模型使用自己的 api_key，否则使用全局配置
        custom_api_key = model_cfg.get("api_key") if is_custom else None
        if custom_api_key:
            auth_value = f"Bearer {custom_api_key}"
        elif settings.spark_api_password:
            auth_value = f"Bearer {settings.spark_api_password}"
        else:
            auth_value = f"Bearer {settings.spark_api_key}:{settings.spark_api_secret}"

        probe_url = model_cfg.get("api_url") or "https://spark-api-open.xf-yun.com/agent/v1/chat/completions"
        probe_model = model_cfg.get("model", current_model)

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                probe_url,
                json={
                    "model": probe_model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 5,
                },
                headers={
                    "Authorization": auth_value,
                    "Content-Type": "application/json",
                },
            )
        latency_ms = round((time.monotonic() - start) * 1000)

        if resp.status_code == 200:
            return {
                "status": "connected",
                "message": f"已连接 {model_cfg.get('label', current_model)}",
                "current_model": current_model,
                "model_label": model_cfg.get("label", current_model),
                "latency_ms": latency_ms,
                "protocol": "http",
                "fallback_mode": False,
            }
        else:
            return {
                "status": "error",
                "message": f"API 返回 HTTP {resp.status_code}",
                "current_model": current_model,
                "model_label": model_cfg.get("label", current_model),
                "latency_ms": latency_ms,
                "protocol": "http",
                "fallback_mode": True,
                "error_detail": resp.text[:200],
            }

    except httpx.TimeoutException:
        return {
            "status": "timeout",
            "message": "API 连接超时",
            "current_model": current_model,
            "model_label": model_cfg.get("label", current_model),
            "latency_ms": None,
            "protocol": "http",
            "fallback_mode": True,
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": f"连接失败: {type(exc).__name__}",
            "current_model": current_model,
            "model_label": model_cfg.get("label", current_model),
            "latency_ms": None,
            "protocol": "http",
            "fallback_mode": True,
            "error_detail": str(exc)[:200],
        }
