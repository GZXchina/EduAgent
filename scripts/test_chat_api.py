"""测试聊天API接口。"""

import asyncio
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import httpx


async def main() -> None:
    print("测试聊天API接口...")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            print("正在发送请求...")
            resp = await client.post(
                "http://127.0.0.1:8001/api/chat",
                json={"message": "你好"},
                headers={"Content-Type": "application/json"},
            )
            print(f"状态码: {resp.status_code}")
            print(f"响应: {resp.text[:2000]}")
    except Exception as e:
        print(f"请求失败: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
