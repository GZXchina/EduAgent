from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import chat, evaluation, health, profile, progress, rag, resources, voice, workflow
from backend.core.logging_config import setup_logging
from backend.core.redis_client import get_redis
from backend.settings import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    from database.session import init_db

    init_db()
    get_redis()

    if settings.auto_ingest_on_startup:
        try:
            from rag.ingest import ingest_knowledge_directory

            n = ingest_knowledge_directory()
            logger.info("启动时自动入库完成，切片数: %s", n)
        except Exception as exc:
            logger.warning("启动时自动入库失败: %s", exc)

    yield


settings = get_settings()

app = FastAPI(
    title="EduAgent API",
    version="0.2.0",
    description="多智能体高校个性化学习平台后端（阶段一～十）",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(rag.router)
app.include_router(profile.router)
app.include_router(voice.router)
app.include_router(evaluation.router)
app.include_router(resources.router)
app.include_router(progress.router)
app.include_router(workflow.router)
