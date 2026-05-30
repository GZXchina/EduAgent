from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime
from time import mktime
from urllib.parse import urlencode, urlparse
from wsgiref.handlers import format_date_time


def build_ws_auth_url(api_key: str, api_secret: str, ws_url: str) -> str:
    """生成带鉴权参数的星火 WebSocket URL（HMAC-SHA256）。"""
    parsed = urlparse(ws_url)
    host = parsed.netloc
    path = parsed.path or "/"

    now = datetime.now()
    date = format_date_time(mktime(now.timetuple()))

    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")

    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")

    query = urlencode({"authorization": authorization, "date": date, "host": host})
    return f"wss://{host}{path}?{query}"
