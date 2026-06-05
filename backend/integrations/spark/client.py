from __future__ import annotations

import json
import logging
import re
import uuid
from functools import lru_cache
from typing import Any

import httpx
import websockets

from backend.integrations.spark.ws_auth import build_ws_auth_url
from backend.settings import get_settings

logger = logging.getLogger(__name__)


# 可用模型配置：model_id → {protocol, model, label, description, ...}
# protocol: "websocket" 或 "http"
# WebSocket 模型需要 ws_url + domain；HTTP 模型需要 api_url
AVAILABLE_MODELS: dict[str, dict[str, str]] = {
    "Spark-X2-Flash": {
        "protocol": "http",
        "model": "spark-x",
        "api_url": "https://spark-api-open.xf-yun.com/agent/v1/chat/completions",
        "label": "Spark X2 Flash",
        "description": "高速推理，国产芯片训练，适合日常对话",
    },
    "Spark-X2": {
        "protocol": "websocket",
        "model": "spark-x",
        "ws_url": "wss://spark-api.xf-yun.com/x2",
        "domain": "spark-x",
        "label": "Spark X2",
        "description": "深度推理模型，综合能力更强",
    },
    "lite": {
        "protocol": "websocket",
        "model": "lite",
        "ws_url": "wss://spark-api.xf-yun.com/v1.1/chat",
        "domain": "lite",
        "label": "Spark Lite",
        "description": "免费轻量版，响应速度快",
    },
    "generalv3": {
        "protocol": "websocket",
        "model": "generalv3",
        "ws_url": "wss://spark-api.xf-yun.com/v3.1/chat",
        "domain": "generalv3",
        "label": "Spark Pro",
        "description": "专业级大模型，性价比高",
    },
    "generalv3.5": {
        "protocol": "websocket",
        "model": "generalv3.5",
        "ws_url": "wss://spark-api.xf-yun.com/v3.5/chat",
        "domain": "generalv3.5",
        "label": "Spark Max",
        "description": "旗舰级大模型，结构化抽取与推理能力强",
    },
}


class SparkClient:
    """讯飞星火客户端：支持 HTTP 开放接口调用多种模型。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return self.settings.spark_configured

    def _use_websocket(self) -> bool:
        s = self.settings
        return (
            s.spark_api_type.lower() == "websocket"
            and bool(s.spark_app_id and s.spark_api_key and s.spark_api_secret and s.spark_ws_url)
        )

    def _auth_header(self) -> dict[str, str]:
        password = self.settings.spark_api_password
        if password:
            return {"Authorization": f"Bearer {password}"}
        return {"Authorization": f"Bearer {self.settings.spark_api_key}:{self.settings.spark_api_secret}"}

    @staticmethod
    def _to_spark_text(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        text: list[dict[str, str]] = []
        for m in messages:
            role = m.get("role", "user")
            content = str(m.get("content", "")).strip()
            if not content:
                continue
            if role in ("system", "user", "assistant"):
                text.append({"role": role, "content": content})
            else:
                text.append({"role": "user", "content": content})
        if text and text[0]["role"] != "system":
            # 无 system 时保持 user/assistant 交替即可
            pass
        return text or [{"role": "user", "content": "你好"}]

    async def _chat_websocket(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        ws_url: str | None = None,
        domain: str | None = None,
    ) -> str:
        s = self.settings
        # 支持模型级别的 ws_url/domain 覆盖
        actual_ws_url = ws_url or s.spark_ws_url
        actual_domain = domain or s.spark_domain
        auth_url = build_ws_auth_url(s.spark_api_key, s.spark_api_secret, actual_ws_url)
        body = {
            "header": {"app_id": s.spark_app_id, "uid": str(uuid.uuid4())[:32]},
            "parameter": {
                "chat": {
                    "domain": actual_domain,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
            },
            "payload": {"message": {"text": self._to_spark_text(messages)}},
        }

        parts: list[str] = []
        async with websockets.connect(
            auth_url,
            ping_interval=None,
            open_timeout=s.spark_timeout,
            close_timeout=s.spark_timeout,
        ) as ws:
            await ws.send(json.dumps(body, ensure_ascii=False))
            while True:
                raw = await ws.recv()
                data = json.loads(raw)
                header = data.get("header") or {}
                code = header.get("code", -1)
                if code != 0:
                    raise RuntimeError(
                        f"星火 WebSocket 错误 code={code}: {header.get('message', data)}"
                    )
                choices = (data.get("payload") or {}).get("choices") or {}
                for item in choices.get("text") or []:
                    parts.append(str(item.get("content", "")))
                if header.get("status") == 2:
                    break

        return "".join(parts).strip()

    def _use_http(self) -> bool:
        s = self.settings
        return (
            s.spark_api_type.lower() == "http"
            and bool(s.spark_app_id and s.spark_api_key and s.spark_api_secret and s.spark_api_url)
        )

    async def _chat_http(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int,
        model: str | None = None,
        api_url: str | None = None,
        api_key: str | None = None,
    ) -> str:
        s = self.settings

        # 确定 API URL 和 model 名称
        # 先从 AVAILABLE_MODELS 查找配置
        if model and model in AVAILABLE_MODELS:
            cfg = AVAILABLE_MODELS[model]
            final_api_url = cfg.get("api_url") or s.spark_api_url
            model_name = cfg["model"]
        elif api_url:
            # 自定义模型传入的配置
            final_api_url = api_url
            model_name = model or s.spark_model
        else:
            final_api_url = s.spark_api_url
            model_name = s.spark_model

        payload = {
            "model": model_name,
            "messages": self._to_spark_text(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        # 构建认证头
        if api_key:
            auth_headers = {"Authorization": f"Bearer {api_key}"}
        else:
            auth_headers = self._auth_header()
        headers = {**auth_headers, "Content-Type": "application/json"}

        logger.info("星火 HTTP 请求: url=%s, model=%s", final_api_url, model_name)
        logger.debug("星火 HTTP payload: %s", json.dumps(payload, ensure_ascii=False)[:500])

        async with httpx.AsyncClient(timeout=s.spark_timeout) as client:
            resp = await client.post(final_api_url, json=payload, headers=headers)
            logger.debug("星火 HTTP 响应状态: %d", resp.status_code)

            if resp.status_code != 200:
                logger.error("星火 HTTP 错误 %d: %s", resp.status_code, resp.text[:500])
                raise RuntimeError(
                    f"星火 HTTP 请求失败 (status={resp.status_code}): {resp.text[:300]}"
                )

            # 处理 SSE 流式响应（部分接口返回 text/event-stream）
            content_type = resp.headers.get("content-type", "")
            if "text/event-stream" in content_type or "event-stream" in content_type:
                return self._parse_sse_response(resp.text)

            data = resp.json()
            logger.debug("星火 HTTP 响应体: %s", json.dumps(data, ensure_ascii=False)[:500])

        # OpenAI 兼容格式解析
        choices = data.get("choices") or []
        if choices:
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if content:
                return str(content).strip()

        # 兜底：尝试从 data 中直接提取 content
        if "content" in data:
            return str(data["content"]).strip()

        raise RuntimeError(f"星火 HTTP 响应无法解析: {json.dumps(data, ensure_ascii=False)[:500]}")

    @staticmethod
    def _parse_sse_response(raw_text: str) -> str:
        """解析 SSE (Server-Sent Events) 流式响应，拼接完整内容。"""
        parts: list[str] = []
        for line in raw_text.split("\n"):
            line = line.strip()
            if not line or not line.startswith("data:"):
                continue
            data_str = line[len("data:"):].strip()
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                choices = chunk.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or choices[0].get("message") or {}
                    content = delta.get("content", "")
                    if content:
                        parts.append(content)
            except json.JSONDecodeError:
                continue
        result = "".join(parts).strip()
        if not result:
            raise RuntimeError(f"星火 SSE 响应无法解析出内容: {raw_text[:300]}")
        return result

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        model: str | None = None,
    ) -> str:
        if not self.configured:
            raise RuntimeError(
                "讯飞星火未配置：请在 .env 中设置 SPARK_APP_ID / SPARK_API_KEY / SPARK_API_SECRET"
            )

        s = self.settings
        model_id = model or s.spark_model

        # 先尝试内置模型配置
        model_cfg = AVAILABLE_MODELS.get(model_id)

        # 如果内置模型不存在，尝试从数据库加载自定义模型
        if not model_cfg and model_id and model_id.startswith("custom-"):
            model_cfg = self._load_custom_model(model_id)

        if model_cfg and model_cfg.get("protocol") == "websocket":
            ws_url = model_cfg.get("ws_url") or s.spark_ws_url
            domain = model_cfg.get("domain") or s.spark_domain
            logger.info("星火请求: WebSocket model=%s, ws_url=%s, domain=%s", model_id, ws_url, domain)
            return await self._chat_websocket(
                messages, temperature=temperature, max_tokens=max_tokens,
                ws_url=ws_url, domain=domain,
            )

        if model_cfg and model_cfg.get("protocol") == "http":
            # HTTP 模型（内置 Spark-X2-Flash 或自定义模型）
            custom_api_url = model_cfg.get("api_url")
            custom_api_key = model_cfg.get("api_key")
            actual_model = model_cfg.get("model", model_id)
            logger.info("星火请求: HTTP model=%s (api_model=%s), api_url=%s", model_id, actual_model, custom_api_url)
            return await self._chat_http(
                messages, temperature=temperature, max_tokens=max_tokens,
                model=actual_model, api_url=custom_api_url, api_key=custom_api_key,
            )

        # 回退到全局配置
        if self._use_websocket():
            logger.debug("星火请求: WebSocket(全局) domain=%s", s.spark_domain)
            return await self._chat_websocket(messages, temperature=temperature, max_tokens=max_tokens)

        if self._use_http():
            logger.debug("星火请求: HTTP(全局) model=%s", model_id)
            return await self._chat_http(messages, temperature=temperature, max_tokens=max_tokens, model=model)

        raise RuntimeError("星火配置不完整：HTTP 需 APP_ID+KEY+SECRET+API_URL")

    def _load_custom_model(self, model_id: str) -> dict[str, str] | None:
        """从数据库加载自定义模型配置"""
        try:
            from database.session import SessionLocal
            from database.models import CustomModel
            db = SessionLocal()
            record = db.query(CustomModel).filter(
                CustomModel.model_id == model_id,
                CustomModel.is_active == 1,
            ).first()
            db.close()
            if record:
                cfg: dict[str, str] = {
                    "protocol": record.protocol,
                    "model": record.model_name,
                    "label": record.label,
                    "description": record.description or "",
                }
                if record.protocol == "http":
                    cfg["api_url"] = record.api_url or ""
                    cfg["api_key"] = record.api_key or ""
                else:
                    cfg["ws_url"] = record.ws_url or ""
                    cfg["domain"] = record.domain or ""
                return cfg
        except Exception as exc:
            logger.warning("加载自定义模型 %s 失败: %s", model_id, exc)
        return None

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        model: str | None = None,
    ) -> dict[str, Any]:
        text = await self.chat(messages, temperature=temperature, model=model)
        return _parse_json_from_text(text)


def _parse_json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    raise ValueError(f"无法从模型输出解析 JSON: {text[:300]}")


@lru_cache
def get_spark_client() -> SparkClient:
    return SparkClient()
