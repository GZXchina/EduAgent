"""测试星火 WebSocket 连接（读取本地 .env，不打印密钥）。"""

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from backend.integrations.spark.client import get_spark_client
from backend.settings import get_settings


async def main() -> None:
    s = get_settings()
    print("configured:", s.spark_configured, "type:", s.spark_api_type, "domain:", s.spark_domain)
    client = get_spark_client()
    text = await client.chat(
        [{"role": "user", "content": "用一句话介绍Python"}],
        temperature=0.3,
        max_tokens=128,
    )
    print("reply:", text[:200])


if __name__ == "__main__":
    asyncio.run(main())
