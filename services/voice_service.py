from __future__ import annotations

import logging
from typing import Any

from backend.integrations.asr import get_asr_client
from backend.integrations.tts import get_tts_client

logger = logging.getLogger(__name__)


class VoiceService:
    """语音服务：封装ASR和TTS，提供语音交互能力。"""

    def __init__(self) -> None:
        self.asr = get_asr_client()
        self.tts = get_tts_client()

    @property
    def asr_configured(self) -> bool:
        return self.asr.configured

    @property
    def tts_configured(self) -> bool:
        return self.tts.configured

    @property
    def configured(self) -> bool:
        return self.asr_configured and self.tts_configured

    async def speech_to_text(self, audio_data: bytes, format: str = "wav") -> str:
        """语音转文字。"""
        if not self.asr_configured:
            raise RuntimeError("ASR未配置")
        return await self.asr.recognize(audio_data, format)

    async def text_to_speech(self, text: str, voice: str = "xiaoyan") -> bytes:
        """文字转语音。"""
        if not self.tts_configured:
            raise RuntimeError("TTS未配置")
        return await self.tts.synthesize(text, voice)

    async def voice_chat(self, audio_data: bytes, format: str = "wav", tts_voice: str = "xiaoyan") -> tuple[str, bytes]:
        """语音对话：识别语音 -> 处理 -> 合成回复语音。"""
        text = await self.speech_to_text(audio_data, format)
        audio = await self.text_to_speech(text, tts_voice)
        return text, audio


def get_voice_service() -> VoiceService:
    return VoiceService()