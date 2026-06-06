from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from functools import lru_cache
from urllib.parse import urlparse, quote

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
        """构建讯飞 TTS WebSocket v2 鉴权 URL。

        鉴权方式：使用 authorization / date / host 查询参数，
        签名算法为 HMAC-SHA256(base64)。
        """
        parsed = urlparse(url)
        host = parsed.hostname or "tts-api.xfyun.cn"
        uri = parsed.path or "/v2/tts"

        # 生成 RFC 1123 格式的 GMT 时间
        date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())

        # 签名原文
        signature_origin = f"host: {host}\ndate: {date}\nGET {uri} HTTP/1.1"

        # HMAC-SHA256 签名（使用 apiSecret 作为密钥）
        signature_sha = hmac.new(
            self.settings.tts_api_secret.encode(),
            signature_origin.encode(),
            digestmod=hashlib.sha256,
        ).digest()

        signature = base64.b64encode(signature_sha).decode()

        # 构建 authorization 原文
        authorization_origin = (
            f'api_key="{self.settings.tts_api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature}"'
        )

        authorization = base64.b64encode(authorization_origin.encode()).decode()

        return f"{url}?authorization={quote(authorization, safe='')}&date={quote(date)}&host={host}"

    async def synthesize(self, text: str, voice: str = "x4_xiaoyan") -> bytes:
        """将文字合成为语音，返回 MP3 音频数据。
        
        Args:
            text: 要合成的文本
            voice: 音色参数名，默认 x4_xiaoyan（通用女声）
                   可选值：x4_xiaoyuan、x4_xiaozhi、x4_xiaomei、x4_xiaomeng 等
        """
        if not self.configured:
            raise RuntimeError("讯飞 TTS 未配置：请在 .env 中设置 TTS_APP_ID / TTS_API_KEY / TTS_API_SECRET")

        url = self._build_auth_url(self.settings.tts_ws_url)
        audio_chunks: list[bytes] = []

        try:
            async with websockets.connect(url, max_size=None, open_timeout=10, close_timeout=10) as ws:
                logger.info("TTS WebSocket 已连接，发送合成请求：voice=%s, text=%s", voice, text[:50])
                await ws.send(json.dumps({
                    "common": {"app_id": self.settings.tts_app_id},
                    "business": {
                        "aue": "lame",
                        "sfl": 1,
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
                        raise RuntimeError(f"TTS 错误 code={code}: {data.get('message', '')}")

                    audio_base64 = data.get("data", {}).get("audio")
                    if audio_base64:
                        audio_chunks.append(base64.b64decode(audio_base64))

                    if data.get("data", {}).get("status") == 2:
                        break

        except websockets.exceptions.WebSocketException as exc:
            logger.error("TTS WebSocket 连接失败：%s", exc)
            raise RuntimeError(f"TTS 连接失败：{exc}")

        if not audio_chunks:
            raise RuntimeError("TTS 未返回任何音频数据")

        return b"".join(audio_chunks)

    async def synthesize_to_file(self, text: str, output_path: str, voice: str = "x4_xiaoyan") -> str:
        """将文字合成为音频文件。
        
        Args:
            text: 要合成的文本
            output_path: 输出文件路径
            voice: 音色参数名，默认 x4_xiaoyan
        """
        audio_data = await self.synthesize(text, voice)
        with open(output_path, "wb") as f:
            f.write(audio_data)
        return output_path


@lru_cache
def get_tts_client() -> TTSClient:
    return TTSClient()
