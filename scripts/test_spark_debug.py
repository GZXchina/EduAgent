"""测试星火 HTTP 连接（详细调试版本）。"""

import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import httpx
from backend.settings import get_settings


async def main() -> None:
    s = get_settings()
    print(f"配置信息:")
    print(f"  app_id: {s.spark_app_id}")
    print(f"  api_key: {s.spark_api_key}")
    print(f"  api_secret: {s.spark_api_secret}")
    print(f"  api_url: {s.spark_api_url}")
    print(f"  model: {s.spark_model}")
    
    payload = {
        "model": s.spark_model,
        "messages": [{"role": "user", "content": "你好"}],
        "temperature": 0.3,
        "max_tokens": 128,
    }
    
    # 测试不同的认证方式
    auth_methods = [
        {"name": "key:secret", "header": f"Bearer {s.spark_api_key}:{s.spark_api_secret}"},
        {"name": "key only", "header": f"Bearer {s.spark_api_key}"},
        {"name": "app_id:key:secret", "header": f"Bearer {s.spark_app_id}:{s.spark_api_key}:{s.spark_api_secret}"},
    ]
    
    for auth in auth_methods:
        headers = {
            "Content-Type": "application/json",
            "Authorization": auth["header"],
        }
        
        print(f"\n=== 测试认证方式: {auth['name']} ===")
        print(f"请求头 Authorization: {auth['header'][:50]}...")
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(s.spark_api_url, json=payload, headers=headers)
                print(f"响应状态: {resp.status_code}")
                print(f"响应体: {resp.text[:1000]}")
        except Exception as e:
            print(f"请求异常: {e}")


if __name__ == "__main__":
    asyncio.run(main())
