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


class ASRClient:
    """讯飞语音听写（流式版）客户端。

    使用 wss://iat-api.xfyun.cn/v2/iat 接口，
    鉴权方式与 TTS v2 相同：authorization / date / host + HMAC-SHA256。
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.asr_app_id and self.settings.asr_api_key and self.settings.asr_api_secret)

    def _build_auth_url(self, url: str) -> str:
        """构建讯飞语音听写 v2 鉴权 URL。

        鉴权方式：使用 authorization / date / host 查询参数，
        签名算法为 HMAC-SHA256(base64)，密钥为 apiSecret。
        """
        parsed = urlparse(url)
        host = parsed.hostname or "iat-api.xfyun.cn"
        uri = parsed.path or "/v2/iat"

        # RFC 1123 格式 GMT 时间
        date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())

        # 签名原文
        signature_origin = f"host: {host}\ndate: {date}\nGET {uri} HTTP/1.1"

        # HMAC-SHA256 签名（使用 apiSecret）
        signature_sha = hmac.new(
            self.settings.asr_api_secret.encode(),
            signature_origin.encode(),
            digestmod=hashlib.sha256,
        ).digest()

        signature = base64.b64encode(signature_sha).decode()

        # 构建 authorization
        authorization_origin = (
            f'api_key="{self.settings.asr_api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature}"'
        )

        authorization = base64.b64encode(authorization_origin.encode()).decode()

        return f"{url}?authorization={quote(authorization, safe='')}&date={quote(date)}&host={host}"

    async def recognize(self, audio_data: bytes, format: str = "wav") -> str:
        """将语音数据识别为文字。"""
        if not self.configured:
            raise RuntimeError("讯飞ASR未配置：请在 .env 中设置 ASR_APP_ID / ASR_API_KEY / ASR_API_SECRET")

        url = self._build_auth_url(self.settings.asr_ws_url)

        # 根据格式确定讯飞 API 的 format 参数
        audio_format = self._get_audio_format(format)
        logger.info("ASR 请求: format=%s, audio_format=%s, size=%d bytes", format, audio_format, len(audio_data))

        sentences: dict[int, str] = {}

        try:
            async with websockets.connect(url, max_size=None, open_timeout=10, close_timeout=10) as ws:
                # 发送音频数据（单帧发送）
                await ws.send(json.dumps({
                    "common": {"app_id": self.settings.asr_app_id},
                    "business": {
                        "language": "zh_cn",
                        "domain": "iat",
                        "accent": "mandarin",
                        "vad_eos": 3000,
                    },
                    "data": {
                        "status": 0,
                        "format": audio_format,
                        "encoding": "raw",
                        "audio": base64.b64encode(audio_data).decode(),
                    },
                }, ensure_ascii=False))

                # 发送结束标志
                await ws.send(json.dumps({
                    "data": {
                        "status": 2,
                        "format": audio_format,
                        "encoding": "raw",
                        "audio": "",
                    },
                }))

                while True:
                    resp = await ws.recv()
                    data = json.loads(resp)
                    code = data.get("code")
                    if code and code != 0:
                        raise RuntimeError(f"ASR错误 code={code}: {data.get('message', '')}")

                    result = data.get("data", {}).get("result", {})
                    sn = result.get("sn", 0)

                    # 提取文本
                    text_parts = []
                    for ws_item in result.get("ws", []):
                        for cw in ws_item.get("cw", []):
                            w = cw.get("w", "")
                            if w:
                                text_parts.append(w)
                    text = "".join(text_parts)

                    # 处理动态修正
                    pgs = result.get("pgs", "apd")
                    if pgs == "rpl":
                        bg = result.get("bg", 0)
                        ed = result.get("ed", 0)
                        for i in range(bg, ed + 1):
                            sentences.pop(i, None)
                    sentences[sn] = text

                    status = data.get("data", {}).get("status", 0)
                    if status == 2:
                        break

        except websockets.exceptions.WebSocketException as exc:
            logger.error("ASR WebSocket连接失败: %s", exc)
            raise RuntimeError(f"ASR连接失败: {exc}")

        final_text = "".join(sentences[k] for k in sorted(sentences.keys()))
        logger.info("ASR 识别结果: %s", final_text[:100] if final_text else "(空)")
        return final_text

    @staticmethod
    def _get_audio_format(format: str) -> str:
        """将文件格式映射为讯飞 ASR API 的 format 参数。"""
        fmt_map = {
            "pcm": "audio/L16;rate=16000",
            "wav": "audio/L16;rate=16000",
            "mp3": "audio/L16;rate=16000",
            "webm": "audio/L16;rate=16000",
        }
        return fmt_map.get(format, "audio/L16;rate=16000")

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
