from __future__ import annotations

import base64
import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import Response

from services.voice_service import get_voice_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])

_voice = get_voice_service()


@router.post("/asr")
async def asr_endpoint(
    audio: Annotated[UploadFile, File(description="语音文件")],
    format: Annotated[str, Form(description="音频格式，wav/mp3/pcm")] = "wav",
) -> dict[str, str]:
    """语音识别：接收语音文件，返回识别文字。"""
    try:
        audio_data = await audio.read()
        text = await _voice.speech_to_text(audio_data, format)
        return {"text": text}
    except RuntimeError as exc:
        logger.warning("ASR请求失败: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("ASR异常: %s", exc)
        raise HTTPException(status_code=500, detail="语音识别失败")


@router.post("/tts")
async def tts_endpoint(
    text: Annotated[str, Form(description="要转换的文字")],
    voice: Annotated[str, Form(description="音色，xiaoyan/aisjiuxu/aisbabyxu")] = "xiaoyan",
) -> Response:
    """语音合成：接收文字，返回音频数据。"""
    try:
        audio_data = await _voice.text_to_speech(text, voice)
        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=speech.mp3"},
        )
    except RuntimeError as exc:
        logger.warning("TTS请求失败: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("TTS异常: %s", exc)
        raise HTTPException(status_code=500, detail="语音合成失败")


@router.get("/status")
def voice_status() -> dict[str, bool]:
    """查询语音服务配置状态。"""
    return {
        "asr_configured": _voice.asr_configured,
        "tts_configured": _voice.tts_configured,
        "fully_configured": _voice.configured,
    }