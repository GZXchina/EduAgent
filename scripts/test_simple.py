"""简单测试：直接测试星火连接。"""

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from backend.integrations.spark.client import get_spark_client


async def main() -> None:
    print("测试星火连接...")
    client = get_spark_client()
    print(f"已配置: {client.configured}")
    
    if not client.configured:
        print("星火未配置")
        return
    
    try:
        text = await client.chat([{"role": "user", "content": "你好"}])
        print(f"星火回复: {text}")
    except Exception as e:
        print(f"星火调用失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
