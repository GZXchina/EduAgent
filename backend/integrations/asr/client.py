from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from functools import lru_cache

import websockets

from backend.settings import get_settings

logger = logging.getLogger(__name__)


class ASRClient:
    """讯飞ASR语音识别客户端。"""

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.asr_app_id and self.settings.asr_api_key and self.settings.asr_api_secret)

    def _build_auth_url(self, url: str) -> str:
        ts = str(int(time.time()))
        app_id = self.settings.asr_app_id
        api_key = self.settings.asr_api_key
        sign_str = app_id + ts
        sign = base64.b64encode(hmac.new(api_key.encode(), sign_str.encode(), digestmod=hashlib.sha256).digest()).decode()
        return f"{url}?appId={app_id}&ts={ts}&sign={sign}"

    async def recognize(self, audio_data: bytes, format: str = "wav") -> str:
        """将语音数据识别为文字。"""
        if not self.configured:
            raise RuntimeError("讯飞ASR未配置：请在 .env 中设置 ASR_APP_ID / ASR_API_KEY / ASR_API_SECRET")

        url = self._build_auth_url(self.settings.asr_ws_url)
        result = []

        try:
            async with websockets.connect(url, max_size=None) as ws:
                await ws.send(json.dumps({
                    "common": {"appId": self.settings.asr_app_id},
                    "business": {"lang": "zh_cn", "domain": "iat"},
                    "data": {
                        "status": 2,
                        "format": f"audio/{format}",
                        "encoding": "raw",
                        "audio": base64.b64encode(audio_data).decode()
                    }
                }, ensure_ascii=False))

                while True:
                    resp = await ws.recv()
                    data = json.loads(resp)
                    code = data.get("code")
                    if code and code != 0:
                        raise RuntimeError(f"ASR错误 code={code}: {data.get('message', '')}")

                    sn = data.get("data", {}).get("sn", 0)
                    result_text = data.get("data", {}).get("text", "")
                    if result_text:
                        result.append(result_text)

                    if data.get("data", {}).get("status") == 2:
                        break

        except websockets.exceptions.WebSocketException as exc:
            logger.error("ASR WebSocket连接失败: %s", exc)
            raise RuntimeError(f"ASR连接失败: {exc}")

        return "".join(result)

    async def recognize_file(self, file_path: str) -> str:
        """识别音频文件。"""
        import pathlib
        audio_bytes = pathlib.Path(file_path).read_bytes()
        if file_path.endswith(".wav"):
            fmt = "wav"
        elif file_path.endswith(".mp3"):
            fmt = "mp3"
        elif file_path.endswith(".pcm"):
            fmt = "pcm"
        else:
            fmt = "wav"
        return await self.recognize(audio_bytes, fmt)


@lru_cache
def get_asr_client() -> ASRClient:
    return ASRClient()