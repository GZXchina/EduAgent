"""阶段一～三冒烟测试（不依赖星火 API）。"""

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from backend.core.logging_config import setup_logging
from backend.core.redis_client import get_redis
from database.session import SessionLocal, init_db
from services.profile_service import ProfileService, heuristic_profile


async def test_profile() -> None:
    init_db()
    db = SessionLocal()
    svc = ProfileService(db, get_redis())
    profile, source = await svc.build_profile(
        "计算机专业，备战蓝桥杯，初学，喜欢图解，每天1小时，循环不会",
        "test-session-001",
        use_cache=False,
    )
    assert profile.knowledge_level == "beginner"
    assert profile.goal == "lanqiao_competition"
    assert source in ("heuristic", "spark", "cache")
    print("profile ok", profile.model_dump(), "source=", source)
    db.close()


def test_heuristic() -> None:
    p = heuristic_profile("软件工程大二，循环薄弱")
    assert p.weakness == "循环"
    print("heuristic ok")


def main() -> None:
    setup_logging()
    test_heuristic()
    asyncio.run(test_profile())
    print("phase 1-3 tests passed")


if __name__ == "__main__":
    main()
