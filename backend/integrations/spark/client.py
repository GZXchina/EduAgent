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


class SparkClient:
    """讯飞星火客户端：优先 WebSocket（v4 Ultra），可选 HTTP 开放接口。"""

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
    ) -> str:
        s = self.settings
        auth_url = build_ws_auth_url(s.spark_api_key, s.spark_api_secret, s.spark_ws_url)
        body = {
            "header": {"app_id": s.spark_app_id, "uid": str(uuid.uuid4())[:32]},
            "parameter": {
                "chat": {
                    "domain": s.spark_domain,
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
    ) -> str:
        s = self.settings
        payload = {
            "model": s.spark_model,
            "messages": self._to_spark_text(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {**self._auth_header(), "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=s.spark_timeout) as client:
            resp = await client.post(s.spark_api_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices") or []
        if choices:
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if content:
                return str(content).strip()

        raise RuntimeError(f"星火 HTTP 响应无法解析: {json.dumps(data, ensure_ascii=False)[:500]}")

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        if not self.configured:
            raise RuntimeError(
                "讯飞星火未配置：请在 .env 中设置 SPARK_APP_ID / SPARK_API_KEY / SPARK_API_SECRET"
            )

        if self._use_websocket():
            logger.debug("星火请求: WebSocket domain=%s", self.settings.spark_domain)
            return await self._chat_websocket(messages, temperature=temperature, max_tokens=max_tokens)

        if self._use_http():
            logger.debug("星火请求: HTTP url=%s", self.settings.spark_api_url)
            return await self._chat_http(messages, temperature=temperature, max_tokens=max_tokens)

        raise RuntimeError("星火配置不完整：HTTP 需 APP_ID+KEY+SECRET+API_URL")

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        text = await self.chat(messages, temperature=temperature)
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
