"""讯飞智文 PPT 生成 API 客户端

接口文档: https://www.xfyun.cn/doc/spark/PPTv2.html
鉴权方式: MD5(appId + timestamp) + HMAC-SHA1
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import asyncio
import time
from typing import Any

import httpx

from backend.settings import get_settings

logger = logging.getLogger(__name__)

BASE_URL = "https://zwapi.xfyun.cn/api/ppt/v2"


class AIPPTClient:
    """讯飞智文 PPT 生成客户端"""

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.aippt_app_id and self.settings.aippt_api_secret)

    def _get_signature(self, timestamp: int) -> str:
        """生成鉴权签名: HMAC-SHA1(MD5(appId + timestamp), secret)"""
        auth = hashlib.md5(f"{self.settings.aippt_app_id}{timestamp}".encode()).hexdigest()
        signature = base64.b64encode(
            hmac.new(
                self.settings.aippt_api_secret.encode(),
                auth.encode(),
                hashlib.sha1,
            ).digest()
        ).decode()
        return signature

    def _get_headers(self) -> dict[str, str]:
        """生成请求头"""
        timestamp = int(time.time())
        signature = self._get_signature(timestamp)
        return {
            "appId": self.settings.aippt_app_id,
            "timestamp": str(timestamp),
            "signature": signature,
            "Content-Type": "application/json; charset=utf-8",
        }

    async def get_template_list(
        self,
        *,
        pay_type: str = "free",
        style: str | None = None,
        color: str | None = None,
        industry: str | None = None,
        page_num: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """获取 PPT 模板列表"""
        headers = self._get_headers()
        body: dict[str, Any] = {
            "payType": pay_type,
            "pageNum": page_num,
            "pageSize": page_size,
        }
        if style:
            body["style"] = style
        if color:
            body["color"] = color
        if industry:
            body["industry"] = industry

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{BASE_URL}/template/list",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    async def create_outline(self, query: str, *, search: bool = False) -> dict[str, Any]:
        """创建 PPT 大纲（使用 form-data 格式，讯飞API要求）"""
        headers = self._get_headers()
        # createOutline 接口要求 form-data 格式，不能用 JSON
        headers.pop("Content-Type", None)
        form_data = {
            "query": query,
            "language": "cn",
            "search": str(search),
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{BASE_URL}/createOutline",
                headers=headers,
                data=form_data,
            )
            resp.raise_for_status()
            return resp.json()

    async def create_ppt(
        self,
        query: str,
        template_id: str,
        *,
        author: str = "EduAgent",
        is_card_note: bool = True,
        search: bool = False,
        is_figure: bool = True,
        ai_image: str = "normal",
    ) -> dict[str, Any]:
        """直接创建 PPT 生成任务（通过内容描述）"""
        headers = self._get_headers()
        # create 接口要求 multipart/form-data 格式
        headers.pop("Content-Type", None)
        form_data = {
            "query": query,
            "templateId": template_id,
            "author": author,
            "isCardNote": str(is_card_note).lower(),
            "search": str(search).lower(),
            "isFigure": str(is_figure).lower(),
            "aiImage": ai_image,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{BASE_URL}/create",
                headers=headers,
                data=form_data,
            )
            resp.raise_for_status()
            return resp.json()

    async def create_ppt_by_outline(
        self,
        query: str,
        outline: str,
        template_id: str,
        *,
        outline_sid: str | None = None,
        author: str = "EduAgent",
        is_card_note: bool = True,
        search: bool = False,
        is_figure: bool = True,
        ai_image: str = "normal",
    ) -> dict[str, Any]:
        """通过大纲创建 PPT 生成任务（JSON格式，outline为JSONObject）"""
        headers = self._get_headers()
        body: dict[str, Any] = {
            "query": query,
            "templateId": template_id,
            "author": author,
            "isCardNote": is_card_note,
            "search": search,
            "isFigure": is_figure,
            "aiImage": ai_image,
        }
        # 优先使用 outlineSid（更可靠），否则传 outline JSON对象
        if outline_sid:
            body["outlineSid"] = outline_sid
        else:
            import json as _json
            try:
                body["outline"] = _json.loads(outline) if isinstance(outline, str) else outline
            except (_json.JSONDecodeError, TypeError):
                body["outline"] = outline

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{BASE_URL}/createPptByOutline",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_progress(self, sid: str) -> dict[str, Any]:
        """查询 PPT 生成任务进度"""
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{BASE_URL}/progress",
                headers=headers,
                params={"sid": sid},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_outline(self, sid: str) -> dict[str, Any]:
        """获取 PPT 大纲内容（用于预览）"""
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{BASE_URL}/outline",
                headers=headers,
                params={"sid": sid},
            )
            resp.raise_for_status()
            return resp.json()

    async def generate_ppt(
        self,
        query: str,
        template_id: str,
        *,
        author: str = "EduAgent",
        is_card_note: bool = True,
        search: bool = False,
        is_figure: bool = True,
        ai_image: str = "normal",
        max_wait_seconds: int = 300,
        poll_interval: int = 3,
    ) -> dict[str, Any]:
        """完整 PPT 生成流程：创建任务 -> 轮询进度 -> 返回结果

        Returns:
            {"sid": str, "ppt_url": str, "status": str, "total_pages": int, "done_pages": int}
        """
        # 1. 创建任务（内容少于200字时先创建大纲）
        if len(query) < 200:
            logger.info("内容较短(%d字)，先创建大纲再生成PPT", len(query))
            outline_resp = await self.create_outline(query, search=search)
            if outline_resp.get("code") != 0:
                raise RuntimeError(f"大纲生成失败: {outline_resp.get('desc', '未知错误')}")
            outline_sid = (outline_resp.get("data") or {}).get("sid", "")
            outline = (outline_resp.get("data") or {}).get("outline", "")
            if not outline_sid and not outline:
                raise RuntimeError("大纲生成结果为空")
            create_resp = await self.create_ppt_by_outline(
                query=query,
                outline=outline or "",
                outline_sid=outline_sid or None,
                template_id=template_id,
                author=author,
                is_card_note=is_card_note,
                search=search,
                is_figure=is_figure,
                ai_image=ai_image,
            )
        else:
            create_resp = await self.create_ppt(
                query=query,
                template_id=template_id,
                author=author,
                is_card_note=is_card_note,
                search=search,
                is_figure=is_figure,
                ai_image=ai_image,
            )

        if create_resp.get("code") != 0:
            raise RuntimeError(f"PPT任务创建失败: {create_resp.get('desc', '未知错误')}")

        sid = (create_resp.get("data") or {}).get("sid")
        if not sid:
            raise RuntimeError("PPT任务创建成功但未返回sid")

        logger.info("PPT任务已创建 sid=%s", sid)

        # 2. 轮询进度
        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            progress = await self.get_progress(sid)
            data = progress.get("data") or {}

            ppt_status = data.get("pptStatus", "")
            ai_image_status = data.get("aiImageStatus", "")
            card_note_status = data.get("cardNoteStatus", "")

            logger.debug(
                "PPT进度 sid=%s ppt=%s image=%s note=%s",
                sid, ppt_status, ai_image_status, card_note_status,
            )

            if ppt_status == "done" and ai_image_status == "done" and card_note_status == "done":
                return {
                    "sid": sid,
                    "ppt_url": data.get("pptUrl", ""),
                    "status": "done",
                    "total_pages": data.get("totalPages", 0),
                    "done_pages": data.get("donePages", 0),
                    "cover_img": data.get("coverImg", ""),
                }

            if ppt_status in ("build_failed", "failed"):
                raise RuntimeError(f"PPT生成失败: {progress.get('desc', '未知错误')}")

            await asyncio.sleep(poll_interval)

        raise RuntimeError(f"PPT生成超时，sid={sid}")


# 全局单例
_aippt_client: AIPPTClient | None = None


def get_aippt_client() -> AIPPTClient:
    global _aippt_client
    if _aippt_client is None:
        _aippt_client = AIPPTClient()
    return _aippt_client
