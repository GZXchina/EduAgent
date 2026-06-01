from __future__ import annotations

import base64
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.video_agent import VideoAgent
from backend.integrations.tts import get_tts_client
from schemas.profile import VideoScript

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/video", tags=["video"])

_video_agent = VideoAgent()
_tts = get_tts_client()


class VideoGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="视频主题，如 Python循环语句")
    session_id: str | None = Field(default=None, description="会话标识")
    tts_voice: str = Field(default="xiaoyan", description="TTS音色，xiaoyan/aisjiuxu/aisbabyxu")


class SceneAudio(BaseModel):
    scene_number: int
    duration: str
    content: str
    visual_description: str
    audio_notes: str | None = None
    audio_base64: str | None = None
    audio_mime: str = "audio/mpeg"


class VideoGenerateResponse(BaseModel):
    topic: str
    total_duration: str
    total_scenes: int
    scenes: list[SceneAudio]
    suggestions: list[str]
    source: str
    tts_available: bool


@router.post("/generate", response_model=VideoGenerateResponse)
async def generate_video(body: VideoGenerateRequest) -> VideoGenerateResponse:
    topic = body.topic
    voice = body.tts_voice

    state: dict[str, Any] = {
        "user_input": topic,
        "session_id": body.session_id,
    }
    result = await _video_agent.run(state)
    script_dict = result.get("video_script")
    if not script_dict:
        raise HTTPException(status_code=500, detail="视频脚本生成失败")

    script = VideoScript(**script_dict)
    logger.info("视频脚本生成完成: topic=%s, scenes=%d, source=%s", script.topic, len(script.scenes), script.source)

    tts_available = _tts.configured
    scenes_with_audio: list[SceneAudio] = []

    for scene in script.scenes:
        narration_text = f"{scene.content}"
        audio_b64: str | None = None

        if tts_available:
            try:
                audio_bytes = await _tts.synthesize(narration_text, voice)
                audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
                logger.info("场景 %d TTS合成成功，音频大小: %d bytes", scene.scene_number, len(audio_bytes))
            except Exception as exc:
                logger.warning("场景 %d TTS合成失败，继续无音频模式: %s", scene.scene_number, exc)

        scenes_with_audio.append(SceneAudio(
            scene_number=scene.scene_number,
            duration=scene.duration,
            content=scene.content,
            visual_description=scene.visual_description,
            audio_notes=scene.audio_notes,
            audio_base64=audio_b64,
        ))

    return VideoGenerateResponse(
        topic=script.topic,
        total_duration=script.total_duration,
        total_scenes=len(scenes_with_audio),
        scenes=scenes_with_audio,
        suggestions=script.suggestions,
        source=script.source,
        tts_available=tts_available,
    )