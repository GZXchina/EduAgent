"""用户自定义 AI 模型 CRUD API"""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database.session import SessionLocal
from database.models import CustomModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/models", tags=["custom_models"])


# ========== Request / Response Schemas ==========

class CustomModelCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=64, description="显示名称")
    description: str = Field(default="", max_length=200)
    provider: str = Field(default="spark", description="spark | openai | deepseek | other")
    protocol: str = Field(default="http", description="http | websocket")
    model_name: str = Field(..., min_length=1, max_length=64, description="模型标识符")
    api_url: str | None = Field(default=None, description="HTTP API 地址")
    api_key: str | None = Field(default=None, description="自定义 API Key")
    ws_url: str | None = Field(default=None, description="WebSocket 地址")
    domain: str | None = Field(default=None, description="Spark Domain")


class CustomModelResponse(BaseModel):
    id: int
    model_id: str
    label: str
    description: str
    provider: str
    protocol: str
    model_name: str
    api_url: str | None
    ws_url: str | None
    domain: str | None
    is_active: bool


class ModelTestResult(BaseModel):
    status: str  # connected | error | timeout
    message: str
    latency_ms: int | None
    fallback_mode: bool


# ========== CRUD Endpoints ==========

@router.get("/custom", response_model=list[CustomModelResponse])
async def list_custom_models() -> list[CustomModelResponse]:
    """列出所有用户自定义模型"""
    db = SessionLocal()
    try:
        models = db.query(CustomModel).filter(CustomModel.is_active == 1).all()
        return [
            CustomModelResponse(
                id=m.id,
                model_id=m.model_id,
                label=m.label,
                description=m.description,
                provider=m.provider,
                protocol=m.protocol,
                model_name=m.model_name,
                api_url=m.api_url,
                ws_url=m.ws_url,
                domain=m.domain,
                is_active=bool(m.is_active),
            )
            for m in models
        ]
    finally:
        db.close()


@router.post("/custom", response_model=CustomModelResponse)
async def create_custom_model(body: CustomModelCreate) -> CustomModelResponse:
    """新增自定义模型"""
    db = SessionLocal()
    try:
        # 生成唯一 model_id: custom-<uuid>
        model_id = f"custom-{uuid.uuid4().hex[:8]}"

        record = CustomModel(
            model_id=model_id,
            label=body.label,
            description=body.description,
            provider=body.provider,
            protocol=body.protocol,
            model_name=body.model_name,
            api_url=body.api_url,
            api_key=body.api_key,
            ws_url=body.ws_url,
            domain=body.domain,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        logger.info("新增自定义模型: %s (%s)", record.label, record.model_id)
        return CustomModelResponse(
            id=record.id,
            model_id=record.model_id,
            label=record.label,
            description=record.description,
            provider=record.provider,
            protocol=record.protocol,
            model_name=record.model_name,
            api_url=record.api_url,
            ws_url=record.ws_url,
            domain=record.domain,
            is_active=bool(record.is_active),
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        db.close()


@router.delete("/custom/{model_id}")
async def delete_custom_model(model_id: str) -> dict:
    """删除自定义模型（软删除）"""
    db = SessionLocal()
    try:
        record = db.query(CustomModel).filter(CustomModel.model_id == model_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="模型不存在")
        record.is_active = 0
        db.commit()
        logger.info("删除自定义模型: %s", model_id)
        return {"ok": True, "message": f"已删除模型 {record.label}"}
    finally:
        db.close()


@router.post("/custom/{model_id}/test", response_model=ModelTestResult)
async def test_custom_model(model_id: str) -> ModelTestResult:
    """测试自定义模型的连通性"""
    db = SessionLocal()
    try:
        record = db.query(CustomModel).filter(
            CustomModel.model_id == model_id,
            CustomModel.is_active == 1,
        ).first()
        if not record:
            raise HTTPException(status_code=404, detail="模型不存在")

        if record.protocol == "websocket":
            return await _test_websocket(record)
        else:
            return await _test_http(record)
    finally:
        db.close()


async def _test_http(record: CustomModel) -> ModelTestResult:
    """HTTP 模型连通性测试"""
    import httpx
    from backend.settings import get_settings

    settings = get_settings()
    api_url = record.api_url or "https://spark-api-open.xf-yun.com/v1/chat/completions"
    api_key = record.api_key or settings.spark_api_password

    if not api_key:
        auth_value = f"Bearer {settings.spark_api_key}:{settings.spark_api_secret}"
    else:
        auth_value = f"Bearer {api_key}"

    try:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                api_url,
                json={
                    "model": record.model_name,
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
            return ModelTestResult(
                status="connected",
                message=f"已连接 {record.label} (HTTP)",
                latency_ms=latency_ms,
                fallback_mode=False,
            )
        else:
            return ModelTestResult(
                status="error",
                message=f"HTTP {resp.status_code}: {resp.text[:100]}",
                latency_ms=latency_ms,
                fallback_mode=True,
            )
    except httpx.TimeoutException:
        return ModelTestResult(
            status="timeout",
            message="连接超时",
            latency_ms=None,
            fallback_mode=True,
        )
    except Exception as exc:
        return ModelTestResult(
            status="error",
            message=f"{type(exc).__name__}: {str(exc)[:100]}",
            latency_ms=None,
            fallback_mode=True,
        )


async def _test_websocket(record: CustomModel) -> ModelTestResult:
    """WebSocket 模型连通性测试"""
    from backend.settings import get_settings

    settings = get_settings()
    ws_url = record.ws_url or settings.spark_ws_url

    try:
        import websockets
        from backend.integrations.spark.ws_auth import build_ws_auth_url

        auth_url = build_ws_auth_url(
            settings.spark_api_key,
            settings.spark_api_secret,
            ws_url,
        )

        start = time.monotonic()
        async with websockets.connect(
            auth_url, ping_interval=None, open_timeout=8, close_timeout=3
        ):
            pass
        latency_ms = round((time.monotonic() - start) * 1000)

        return ModelTestResult(
            status="connected",
            message=f"已连接 {record.label} (WebSocket)",
            latency_ms=latency_ms,
            fallback_mode=False,
        )
    except Exception as exc:
        return ModelTestResult(
            status="error",
            message=f"WebSocket 失败: {type(exc).__name__}",
            latency_ms=None,
            fallback_mode=True,
        )
