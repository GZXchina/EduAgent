"""
讯飞智文 PPT 生成 API

双模式架构：
- 在线模式（默认）: 讯飞智文API云端生成，异步轮询进度
- 本地模式: 选中对话模型生成内容 + python-pptx本地渲染，同步返回.pptx文件

在线模式流程（异步非阻塞）:
1. 用户输入原始提示词
2. 提示词优化与模板获取并行执行
3. 将优化后的提示词发送给讯飞智文 PPT v2 API 创建任务
4. 立即返回 sid，前端轮询 /progress 获取进度
5. 生成完成后可通过 /outline 预览大纲内容

本地模式流程（同步）:
1. 用户输入主题 + 选择对话模型
2. 调用对话模型生成 PPTDeck JSON（失败降级为规则模板）
3. python-pptx 渲染为 .pptx 文件
4. 直接返回文件流供浏览器下载

关键设计：
- 在线模式：提示词优化使用对话模型，PPT生成使用讯飞智文API
- 本地模式：对话模型生成内容，python-pptx本地渲染
- 两个模型职责分离：优化模型负责理解需求，PPT模型负责生成演示文稿
- 异步非阻塞：在线模式 generate 立即返回 sid，前端轮询进度
- 本地模式同步返回 .pptx 文件流，无需轮询
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.integrations.aippt.client import get_aippt_client
from backend.integrations.spark.client import get_spark_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/aippt", tags=["aippt"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class PPTGenerateRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000, description="用户原始PPT需求描述")
    template_id: str = Field(default="", description="PPT模板ID，空则自动选择免费模板")
    optimize_model: str | None = Field(
        default=None,
        description="用于提示词优化的对话模型ID（如 Spark-X2-Flash、generalv3.5）。"
                    "为空则使用默认模型。注意：不能是PPT生成模型，PPT生成固定使用讯飞智文API。",
    )
    optimize_prompt: bool = Field(default=True, description="是否先调用对话模型优化提示词（推荐开启）")
    author: str = Field(default="EduAgent", description="PPT作者名")
    is_card_note: bool = Field(default=True, description="是否生成演讲备注")
    search: bool = Field(default=False, description="是否联网搜索补充内容")
    is_figure: bool = Field(default=True, description="是否自动配图")
    ai_image: str = Field(default="normal", description="AI配图类型: normal/advanced")


class PPTGenerateResponse(BaseModel):
    sid: str = Field(description="任务ID")
    ppt_url: str = Field(description="PPT下载链接")
    status: str = Field(description="任务状态")
    total_pages: int = Field(description="总页数")
    done_pages: int = Field(description="已完成页数")
    cover_img: str = Field(default="", description="封面图片URL")
    original_query: str = Field(description="用户原始提示词")
    optimized_query: str = Field(description="优化后的提示词（发送给PPT生成API的）")
    prompt_optimized: bool = Field(description="提示词是否经过优化")


class PPTProgressRequest(BaseModel):
    sid: str = Field(..., description="任务ID")


class PPTProgressResponse(BaseModel):
    sid: str = Field(description="任务ID")
    status: str = Field(description="整体状态: done/building/failed")
    ppt_status: str = Field(description="PPT生成状态")
    ai_image_status: str = Field(description="配图状态")
    card_note_status: str = Field(description="演讲备注状态")
    total_pages: int = Field(description="总页数")
    done_pages: int = Field(description="已完成页数")
    ppt_url: str = Field(default="", description="PPT下载链接")
    cover_img: str = Field(default="", description="封面图片URL")
    progress_percent: int = Field(description="进度百分比")


class TemplateListResponse(BaseModel):
    templates: list[dict[str, Any]] = Field(description="模板列表")


# ---------------------------------------------------------------------------
# 提示词优化 - 使用非PPT对话模型
# ---------------------------------------------------------------------------

# 明确排除的模型ID：这些是PPT生成专用模型，不能用于对话优化
_NON_CHAT_MODEL_IDS = frozenset({"aippt", "ppt", "ppt_generator"})

PROMPT_OPTIMIZE_SYSTEM = """你是一位专业的PPT内容策划师。你的任务是将用户的简单需求描述优化为适合AI生成PPT的详细提示词。

优化原则：
1. 补充明确的主题、目标受众、使用场景
2. 添加内容结构建议（章节划分）
3. 指定风格偏好（商务、学术、简约等）
4. 保持中文，输出一段连贯的提示词
5. 不要输出任何解释，只输出优化后的提示词

示例：
用户输入：Python循环语句
优化后：请生成一份关于Python循环语句的教学PPT，面向编程初学者。内容包含：for循环基础语法、while循环使用场景、循环控制语句break/continue、列表推导式、常见错误与调试技巧。风格要求：简洁清晰，代码高亮，配有流程图示意。"""


async def _optimize_prompt(query: str, optimize_model: str | None = None) -> str:
    """调用非PPT对话模型优化用户提示词。

    重要：此函数始终使用对话模型（Spark-X2、generalv3.5等），
    绝不使用PPT生成模型。PPT生成由讯飞智文API独立完成。
    """
    spark = get_spark_client()
    if not spark.configured:
        logger.warning("对话模型未配置，跳过提示词优化，使用原始输入")
        return query

    # 安全检查：如果传入的模型ID是PPT生成模型，强制切换到默认模型
    if optimize_model and optimize_model.lower() in _NON_CHAT_MODEL_IDS:
        logger.warning(
            "optimize_model='%s' 是PPT生成模型，不支持对话优化，切换到默认对话模型",
            optimize_model,
        )
        optimize_model = None

    if optimize_model:
        logger.info("提示词优化使用模型: %s", optimize_model)
    else:
        logger.info("提示词优化使用默认对话模型")

    messages = [
        {"role": "system", "content": PROMPT_OPTIMIZE_SYSTEM},
        {"role": "user", "content": f"请优化以下PPT生成需求：\n\n{query}"},
    ]

    try:
        optimized = await spark.chat(messages, model=optimize_model, temperature=0.5, max_tokens=1024)
        optimized = optimized.strip()
        if optimized and len(optimized) > 10:
            logger.info(
                "提示词优化完成: 原始长度=%d, 优化后长度=%d, 预览=%.80s...",
                len(query), len(optimized), optimized,
            )
            return optimized
        else:
            logger.warning("提示词优化结果太短(%d字)，使用原始提示词", len(optimized))
    except Exception as exc:
        logger.warning("提示词优化失败: %s，使用原始提示词", exc)

    return query


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=PPTGenerateResponse)
async def generate_ppt(body: PPTGenerateRequest) -> PPTGenerateResponse:
    """生成PPT（异步非阻塞）：提示词优化 → PPT任务创建 → 立即返回sid

    架构优化：
    - 提示词优化与模板获取并行执行，节省串行等待时间
    - 不再后端轮询等待PPT完成，立即返回sid供前端轮询
    - 前端通过 /progress 轮询进度，通过 /outline 预览大纲
    """
    aippt = get_aippt_client()
    if not aippt.configured:
        raise HTTPException(status_code=503, detail="讯飞智文PPT服务未配置")

    original_query = body.query

    # 并行执行：提示词优化 + 模板获取
    optimize_coro = _optimize_prompt(body.query, body.optimize_model) if body.optimize_prompt else _identity(body.query)
    template_coro = _get_template_id(body.template_id)
    optimized, template_id = await asyncio.gather(optimize_coro, template_coro)

    prompt_optimized = body.optimize_prompt and optimized != body.query
    query = optimized

    logger.info(
        "PPT生成流程: optimize=%s, model=%s, query长度=%d, template_id=%s",
        prompt_optimized, body.optimize_model or "default", len(query), template_id,
    )

    # 创建PPT任务（不轮询等待完成，立即返回sid）
    try:
        if len(query) < 200:
            outline_resp = await aippt.create_outline(query, search=body.search)
            if outline_resp.get("code") != 0:
                raise RuntimeError(f"大纲生成失败: {outline_resp.get('desc', '未知错误')}")
            outline_sid = (outline_resp.get("data") or {}).get("sid", "")
            outline = (outline_resp.get("data") or {}).get("outline", "")
            create_resp = await aippt.create_ppt_by_outline(
                query=query,
                outline=outline or "",
                outline_sid=outline_sid or None,
                template_id=template_id,
                author=body.author,
                is_card_note=body.is_card_note,
                search=body.search,
                is_figure=body.is_figure,
                ai_image=body.ai_image,
            )
        else:
            create_resp = await aippt.create_ppt(
                query=query,
                template_id=template_id,
                author=body.author,
                is_card_note=body.is_card_note,
                search=body.search,
                is_figure=body.is_figure,
                ai_image=body.ai_image,
            )
    except Exception as exc:
        logger.exception("讯飞智文PPT任务创建失败")
        raise HTTPException(status_code=500, detail=f"PPT任务创建失败: {exc}") from exc

    if create_resp.get("code") != 0:
        raise HTTPException(status_code=400, detail=f"PPT任务创建失败: {create_resp.get('desc', '未知错误')}")

    sid = (create_resp.get("data") or {}).get("sid", "")
    if not sid:
        raise HTTPException(status_code=500, detail="PPT任务创建成功但未返回sid")

    logger.info("PPT任务已创建 sid=%s，前端将轮询进度", sid)

    return PPTGenerateResponse(
        sid=sid,
        ppt_url="",
        status="building",
        total_pages=0,
        done_pages=0,
        cover_img="",
        original_query=original_query,
        optimized_query=query,
        prompt_optimized=prompt_optimized,
    )


async def _identity(text: str) -> str:
    """不优化时直接返回原始文本"""
    return text


async def _get_template_id(template_id: str) -> str:
    """获取模板ID，如果未指定则自动选择免费模板"""
    if template_id:
        return template_id

    aippt = get_aippt_client()
    try:
        tpl_resp = await aippt.get_template_list(pay_type="free", page_size=1)
        if tpl_resp.get("code") == 0:
            templates = (tpl_resp.get("data") or {}).get("records", [])
            if templates:
                return templates[0].get("templateIndexId", "")
    except Exception as exc:
        logger.warning("获取默认模板失败: %s", exc)

    return "20240718489569D"  # 兜底模板ID


@router.post("/progress", response_model=PPTProgressResponse)
async def get_progress(body: PPTProgressRequest) -> PPTProgressResponse:
    """查询PPT生成任务进度"""
    aippt = get_aippt_client()
    if not aippt.configured:
        raise HTTPException(status_code=503, detail="讯飞智文PPT服务未配置")

    try:
        resp = await aippt.get_progress(body.sid)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"查询进度失败: {exc}") from exc

    if resp.get("code") != 0:
        raise HTTPException(status_code=400, detail=resp.get("desc", "查询失败"))

    data = resp.get("data") or {}
    total = data.get("totalPages", 0)
    done = data.get("donePages", 0)
    percent = int(done / total * 100) if total > 0 else 0

    # 判断整体状态
    ppt_status = data.get("pptStatus", "")
    img_status = data.get("aiImageStatus", "")
    note_status = data.get("cardNoteStatus", "")

    if ppt_status == "done" and img_status == "done" and note_status == "done":
        status = "done"
    elif ppt_status in ("build_failed", "failed"):
        status = "failed"
    else:
        status = "building"

    return PPTProgressResponse(
        sid=body.sid,
        status=status,
        ppt_status=ppt_status,
        ai_image_status=img_status,
        card_note_status=note_status,
        total_pages=total,
        done_pages=done,
        ppt_url=data.get("pptUrl", ""),
        cover_img=data.get("coverImg", ""),
        progress_percent=percent,
    )


class PPTOutlineResponse(BaseModel):
    sid: str = Field(description="任务ID")
    title: str = Field(default="", description="PPT标题")
    sub_title: str = Field(default="", description="PPT副标题")
    outline: str = Field(default="", description="PPT大纲JSON字符串")
    outline_parsed: list[dict[str, Any]] = Field(default=[], description="解析后的大纲结构")


@router.get("/outline", response_model=PPTOutlineResponse)
async def get_outline(sid: str) -> PPTOutlineResponse:
    """获取PPT大纲内容（用于预览）"""
    aippt = get_aippt_client()
    if not aippt.configured:
        raise HTTPException(status_code=503, detail="讯飞智文PPT服务未配置")

    try:
        resp = await aippt.get_outline(sid)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取大纲失败: {exc}") from exc

    if resp.get("code") != 0:
        raise HTTPException(status_code=400, detail=resp.get("desc", "获取大纲失败"))

    data = resp.get("data") or {}
    outline_raw = data.get("outline", "")

    # 尝试解析大纲JSON
    outline_parsed: list[dict[str, Any]] = []
    if outline_raw:
        import json
        try:
            parsed = json.loads(outline_raw) if isinstance(outline_raw, str) else outline_raw
            if isinstance(parsed, list):
                outline_parsed = parsed
            elif isinstance(parsed, dict):
                # 有些格式是 {chapters: [...]} 或直接就是大纲对象
                outline_parsed = parsed.get("chapters", parsed.get("sections", [parsed]))
        except (json.JSONDecodeError, TypeError):
            outline_parsed = [{"raw": outline_raw}]

    return PPTOutlineResponse(
        sid=sid,
        title=data.get("title", ""),
        sub_title=data.get("subTitle", ""),
        outline=outline_raw if isinstance(outline_raw, str) else str(outline_raw),
        outline_parsed=outline_parsed,
    )


@router.get("/templates", response_model=TemplateListResponse)
async def get_templates(
    pay_type: str = "free",
    style: str | None = None,
    color: str | None = None,
    industry: str | None = None,
    page_num: int = 1,
    page_size: int = 20,
) -> TemplateListResponse:
    """获取PPT模板列表"""
    aippt = get_aippt_client()
    if not aippt.configured:
        raise HTTPException(status_code=503, detail="讯飞智文PPT服务未配置")

    try:
        resp = await aippt.get_template_list(
            pay_type=pay_type,
            style=style,
            color=color,
            industry=industry,
            page_num=page_num,
            page_size=page_size,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取模板失败: {exc}") from exc

    if resp.get("code") != 0:
        raise HTTPException(status_code=400, detail=resp.get("desc", "获取失败"))

    templates = (resp.get("data") or {}).get("records", [])
    return TemplateListResponse(templates=templates)


# ---------------------------------------------------------------------------
# 本地模式：对话模型生成内容 + python-pptx 渲染
# ---------------------------------------------------------------------------

from fastapi.responses import Response as FastAPIResponse

from backend.integrations.pptx_builder.renderer import PPTXRenderer
from schemas.profile import PPTDeck


class PPTLocalGenerateRequest(BaseModel):
    """本地模式 PPT 生成请求"""
    query: str = Field(..., min_length=1, max_length=8000, description="PPT主题")
    model: str | None = Field(default=None, description="对话模型ID，为空则使用默认模型")
    theme: str = Field(default="default", description="PPT主题风格: default/dark/education")
    author: str = Field(default="EduAgent", description="PPT作者名")


# PPT内容生成系统提示词
_PPT_CONTENT_SYSTEM = """你是一位专业的PPT内容策划师。根据用户提供的主题，生成结构化的PPT课件内容。

输出严格的JSON格式：
{
  "topic": "主题名称",
  "total_slides": 页数,
  "slides": [
    {
      "slide_number": 1,
      "title": "页面标题",
      "content": ["要点1", "要点2", "要点3"],
      "notes": "演讲备注（可选）"
    }
  ]
}

要求：
1. 生成6-10页幻灯片，内容充实有深度
2. 第一页为概述/导言，最后一页为总结
3. 每页3-6个要点，简洁精炼
4. 演讲备注提供补充说明
5. 只输出JSON，不要任何其他文字"""


@router.post("/generate-local")
async def generate_ppt_local(body: PPTLocalGenerateRequest) -> FastAPIResponse:
    """本地模式生成PPT：对话模型生成内容 + python-pptx渲染

    流程：
    1. 调用选中对话模型生成 PPTDeck JSON
    2. 失败时降级为规则模板
    3. python-pptx 渲染为 .pptx 文件
    4. 直接返回文件流
    """
    try:
        deck = await _generate_ppt_content(body.query, body.model)
    except Exception as exc:
        logger.exception("PPT内容生成失败")
        raise HTTPException(status_code=500, detail=f"PPT内容生成失败: {exc}") from exc

    try:
        renderer = PPTXRenderer(theme=body.theme)
        pptx_bytes = renderer.render(deck)
    except Exception as exc:
        logger.exception("python-pptx渲染失败")
        raise HTTPException(status_code=500, detail=f"PPT渲染失败: {exc}") from exc

    # RFC 5987 编码中文文件名，避免 header 非ASCII字符导致 500
    from urllib.parse import quote
    ascii_name = f"presentation_{deck.topic[:20].replace(' ', '_')}.pptx"
    encoded_name = quote(ascii_name)

    return FastAPIResponse(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f"attachment; filename=\"{encoded_name}\"; filename*=UTF-8''{encoded_name}",
        },
    )


async def _generate_ppt_content(query: str, model: str | None = None) -> PPTDeck:
    """调用对话模型生成 PPTDeck 内容，失败降级为规则模板"""
    spark = get_spark_client()

    if spark.configured:
        try:
            deck = await _generate_with_chat_model(spark, query, model)
            logger.info("对话模型生成PPT内容成功: topic=%s, model=%s", deck.topic, model or "default")
            return deck
        except Exception as exc:
            logger.warning("对话模型生成PPT内容失败，降级为规则模板: %s", exc)

    # 降级为规则模板
    from agents.ppt_agent import heuristic_ppt
    logger.info("使用规则模板生成PPT内容: topic=%s", query)
    return heuristic_ppt(query)


async def _generate_with_chat_model(
    spark: Any,
    query: str,
    model: str | None = None,
) -> PPTDeck:
    """调用对话模型生成结构化PPT内容"""
    messages = [
        {"role": "system", "content": _PPT_CONTENT_SYSTEM},
        {"role": "user", "content": f"请为主题「{query}」生成PPT课件内容"},
    ]

    data = await spark.chat_json(messages, model=model, temperature=0.7)
    data.setdefault("source", "chat_model")
    return PPTDeck.model_validate(data)


# ---------------------------------------------------------------------------
# HTML 演示模式：对话模型生成内容 + html-ppt-skill 渲染
# ---------------------------------------------------------------------------

from backend.integrations.html_ppt_builder.renderer import HTMLPPTRenderer, AVAILABLE_THEMES


class PPTHtmlGenerateRequest(BaseModel):
    """HTML 演示模式 PPT 生成请求"""
    query: str = Field(..., min_length=1, max_length=8000, description="PPT主题")
    model: str | None = Field(default=None, description="对话模型ID")
    theme: str = Field(default="corporate-clean", description="HTML主题风格")
    with_presenter: bool = Field(default=False, description="是否含演讲者逐字稿")


@router.post("/generate-html")
async def generate_ppt_html(body: PPTHtmlGenerateRequest) -> dict:
    """HTML演示模式：AI生成内容 + html-ppt-skill渲染

    流程：
    1. 调用选中对话模型生成 PPTDeck JSON
    2. 失败时降级为规则模板
    3. html-ppt-skill 渲染为可交互 HTML
    4. 返回 HTML 字符串供前端 iframe 预览
    """
    try:
        deck = await _generate_ppt_content(body.query, body.model)
    except Exception as exc:
        logger.exception("PPT内容生成失败")
        raise HTTPException(status_code=500, detail=f"PPT内容生成失败: {exc}") from exc

    try:
        renderer = HTMLPPTRenderer(
            theme=body.theme,
            with_presenter=body.with_presenter,
        )
        html = renderer.render(deck)
    except Exception as exc:
        logger.exception("HTML渲染失败")
        raise HTTPException(status_code=500, detail=f"HTML渲染失败: {exc}") from exc

    return {
        "html": html,
        "topic": deck.topic,
        "total_slides": deck.total_slides,
        "theme": body.theme,
    }


@router.get("/html-themes")
async def list_html_themes() -> dict:
    """获取可用的 HTML PPT 主题列表"""
    return {"themes": [{"id": k, "label": v} for k, v in AVAILABLE_THEMES.items()]}
