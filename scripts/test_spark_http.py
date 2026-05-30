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
    print(f"  app_id: {s.spark_app_id[:8]}...")
    print(f"  api_key: {s.spark_api_key[:8]}...")
    print(f"  api_secret: {s.spark_api_secret[:8]}...")
    print(f"  api_url: {s.spark_api_url}")
    print(f"  domain: {s.spark_domain}")
    
    # 构建认证头
    auth_str = f'api_key="{s.spark_api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="test"'
    import base64
    auth_b64 = base64.b64encode(auth_str.encode()).decode()
    
    # 测试请求
    payload = {
        "header": {"app_id": s.spark_app_id},
        "parameter": {
            "chat": {
                "domain": s.spark_domain,
                "temperature": 0.3,
                "max_tokens": 128,
            }
        },
        "payload": {"message": {"text": [{"role": "user", "content": "你好"}]}},
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {s.spark_api_key}:{s.spark_api_secret}",
    }
    
    print(f"\n发送请求到: {s.spark_api_url}")
    print(f"请求头: {json.dumps(headers, ensure_ascii=False)}")
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(s.spark_api_url, json=payload, headers=headers)
            print(f"\n响应状态: {resp.status_code}")
            print(f"响应头: {dict(resp.headers)}")
            print(f"响应体: {resp.text[:1000]}")
    except Exception as e:
        print(f"请求异常: {e}")


if __name__ == "__main__":
    asyncio.run(main())
