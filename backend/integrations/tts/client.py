from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from functools import lru_cache
from typing import AsyncIterator

import websockets

from backend.settings import get_settings

logger = logging.getLogger(__name__)


class TTSClient:
    """讯飞TTS语音合成客户端。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.tts_app_id and self.settings.tts_api_key and self.settings.tts_api_secret)

    def _build_auth_url(self, url: str) -> str:
        ts = str(int(time.time()))
        app_id = self.settings.tts_app_id
        api_key = self.settings.tts_api_key
        sign_str = app_id + ts
        sign = base64.b64encode(hmac.new(api_key.encode(), sign_str.encode(), digestmod=hashlib.sha256).digest()).decode()
        return f"{url}?appId={app_id}&ts={ts}&sign={sign}"

    async def synthesize(self, text: str, voice: str = "xiaoyan") -> bytes:
        """将文字合成为语音，返回PCM/WAV格式音频数据。"""
        if not self.configured:
            raise RuntimeError("讯飞TTS未配置：请在 .env 中设置 TTS_APP_ID / TTS_API_KEY / TTS_API_SECRET")

        url = self._build_auth_url(self.settings.tts_ws_url)
        audio_chunks: list[bytes] = []

        try:
            async with websockets.connect(url, max_size=None) as ws:
                await ws.send(json.dumps({
                    "common": {"appId": self.settings.tts_app_id},
                    "business": {
                        "aue": "lame",
                        "auf": "audio/L16;rate=16000",
                        "vcn": voice,
                        "speed": 50,
                        "volume": 50,
                        "pitch": 50,
                        "tte": "utf8"
                    },
                    "data": {
                        "status": 2,
                        "text": base64.b64encode(text.encode("utf-8")).decode("ascii")
                    }
                }, ensure_ascii=False))

                while True:
                    resp = await ws.recv()
                    data = json.loads(resp)
                    code = data.get("code")
                    if code and code != 0:
                        raise RuntimeError(f"TTS错误 code={code}: {data.get('message', '')}")

                    audio_base64 = data.get("data", {}).get("audio")
                    if audio_base64:
                        audio_chunks.append(base64.b64decode(audio_base64))

                    if data.get("data", {}).get("status") == 2:
                        break

        except websockets.exceptions.WebSocketException as exc:
            logger.error("TTS WebSocket连接失败: %s", exc)
            raise RuntimeError(f"TTS连接失败: {exc}")

        if not audio_chunks:
            raise RuntimeError("TTS未返回任何音频数据")

        return b"".join(audio_chunks)

    async def synthesize_to_file(self, text: str, output_path: str, voice: str = "xiaoyan") -> str:
        """将文字合成为音频文件。"""
        audio_data = await self.synthesize(text, voice)
        with open(output_path, "wb") as f:
            f.write(audio_data)
        return output_path


@lru_cache
def get_tts_client() -> TTSClient:
    return TTSClient()