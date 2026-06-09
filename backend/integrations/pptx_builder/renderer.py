"""python-pptx 渲染器：将 PPTDeck 数据渲染为 .pptx 文件。

支持三套内置主题：
- default: 蓝白商务风
- dark: 深色主题
- education: 浅色学术风

架构定位：
- 本地 PPT 生成模式的核心渲染层
- 接收 schemas.profile.PPTDeck 数据，输出 .pptx 字节流
- 与 AI 模型生成内容解耦：AI 只负责生成结构化内容，渲染由本模块独立完成
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

from schemas.profile import PPTDeck, PPTSlide

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 主题配色
# ---------------------------------------------------------------------------

class _ThemeColors:
    """主题配色方案"""
    def __init__(
        self,
        name: str,
        primary: RGBColor,
        primary_dark: RGBColor,
        accent: RGBColor,
        accent_light: RGBColor,
        bg: RGBColor,
        text: RGBColor,
        text_secondary: RGBColor,
        card_bg: RGBColor,
        card_border: RGBColor,
    ):
        self.name = name
        self.primary = primary
        self.primary_dark = primary_dark
        self.accent = accent
        self.accent_light = accent_light
        self.bg = bg
        self.text = text
        self.text_secondary = text_secondary
        self.card_bg = card_bg
        self.card_border = card_border


THEMES: dict[str, _ThemeColors] = {
    "default": _ThemeColors(
        name="蓝白商务",
        primary=RGBColor(0x1A, 0x56, 0xDB),
        primary_dark=RGBColor(0x0F, 0x3B, 0x99),
        accent=RGBColor(0x10, 0xB9, 0x81),
        accent_light=RGBColor(0xD1, 0xFA, 0xE5),
        bg=RGBColor(0xFF, 0xFF, 0xFF),
        text=RGBColor(0x1F, 0x29, 0x37),
        text_secondary=RGBColor(0x6B, 0x72, 0x80),
        card_bg=RGBColor(0xFF, 0xFF, 0xFF),
        card_border=RGBColor(0xE5, 0xE7, 0xEB),
    ),
    "dark": _ThemeColors(
        name="深色主题",
        primary=RGBColor(0x3B, 0x82, 0xF6),
        primary_dark=RGBColor(0x1D, 0x4E, 0xD8),
        accent=RGBColor(0x10, 0xB9, 0x81),
        accent_light=RGBColor(0x06, 0x4E, 0x3B),
        bg=RGBColor(0x0F, 0x17, 0x2A),
        text=RGBColor(0xF3, 0xF4, 0xF6),
        text_secondary=RGBColor(0x93, 0xA3, 0xBA),
        card_bg=RGBColor(0x1E, 0x29, 0x3B),
        card_border=RGBColor(0x37, 0x41, 0x51),
    ),
    "education": _ThemeColors(
        name="浅色学术",
        primary=RGBColor(0x7C, 0x3A, 0xED),
        primary_dark=RGBColor(0x5B, 0x21, 0xB6),
        accent=RGBColor(0xF5, 0x9E, 0x0B),
        accent_light=RGBColor(0xFE, 0xF3, 0xC7),
        bg=RGBColor(0xFA, 0xFA, 0xFA),
        text=RGBColor(0x1F, 0x29, 0x37),
        text_secondary=RGBColor(0x6B, 0x72, 0x80),
        card_bg=RGBColor(0xFF, 0xFF, 0xFF),
        card_border=RGBColor(0xE5, 0xE7, 0xEB),
    ),
}

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
FONT_NAME = "Microsoft YaHei"


# ---------------------------------------------------------------------------
# 渲染器
# ---------------------------------------------------------------------------

class PPTXRenderer:
    """将 PPTDeck 渲染为 .pptx 文件"""

    def __init__(self, theme: str = "default") -> None:
        self.theme = THEMES.get(theme, THEMES["default"])

    def render(self, deck: PPTDeck) -> bytes:
        """渲染 PPTDeck 为 .pptx 字节流"""
        prs = self._create_presentation()
        self._render_cover(prs, deck)
        self._render_toc(prs, deck)
        for slide_data in deck.slides:
            self._render_content_slide(prs, slide_data, deck)
        self._render_end(prs, deck)

        buf = io.BytesIO()
        prs.save(buf)
        buf.seek(0)
        logger.info("PPTX渲染完成: %s, %d页", deck.topic, len(prs.slides))
        return buf.getvalue()

    def render_to_file(self, deck: PPTDeck, path: Path) -> Path:
        """渲染并保存到文件"""
        data = self.render(deck)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        logger.info("PPTX已保存: %s", path)
        return path

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _create_presentation(self) -> Presentation:
        prs = Presentation()
        prs.slide_width = SLIDE_W
        prs.slide_height = SLIDE_H
        return prs

    def _add_bg(self, slide: Any, color: RGBColor) -> None:
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = color

    def _add_textbox(
        self,
        slide: Any,
        left: float, top: float, width: float, height: float,
        text: str,
        font_size: int = 18,
        color: RGBColor | None = None,
        bold: bool = False,
        align: Any = PP_ALIGN.LEFT,
    ) -> Any:
        if color is None:
            color = self.theme.text
        txBox = slide.shapes.add_textbox(
            Inches(left), Inches(top), Inches(width), Inches(height)
        )
        tf = txBox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = text
        p.font.size = Pt(font_size)
        p.font.color.rgb = color
        p.font.bold = bold
        p.font.name = FONT_NAME
        p.alignment = align
        return tf

    def _add_shape(
        self,
        slide: Any,
        left: float, top: float, width: float, height: float,
        fill_color: RGBColor | None = None,
    ) -> Any:
        shape = slide.shapes.add_shape(
            1, Inches(left), Inches(top), Inches(width), Inches(height)
        )
        if fill_color:
            shape.fill.solid()
            shape.fill.fore_color.rgb = fill_color
        else:
            shape.fill.background()
        shape.line.fill.background()
        return shape

    def _add_bullet_list(
        self,
        tf: Any,
        items: list[str],
        font_size: int = 16,
        color: RGBColor | None = None,
        spacing: int = 6,
    ) -> None:
        if color is None:
            color = self.theme.text
        for i, item in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = f"  {item}"
            p.font.size = Pt(font_size)
            p.font.color.rgb = color
            p.font.name = FONT_NAME
            p.space_after = Pt(spacing)

    def _slide_number(self, slide: Any, num: int) -> None:
        self._add_textbox(
            slide, 12.3, 7.0, 0.8, 0.4, str(num),
            font_size=10, color=self.theme.text_secondary, align=PP_ALIGN.RIGHT,
        )

    # ------------------------------------------------------------------
    # 页面渲染
    # ------------------------------------------------------------------

    def _render_cover(self, prs: Presentation, deck: PPTDeck) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        self._add_bg(slide, self.theme.primary_dark)

        # 装饰线
        self._add_shape(slide, 1.5, 2.8, 2.0, 0.06, fill_color=self.theme.accent)

        self._add_textbox(
            slide, 1.5, 1.5, 10, 1.0, deck.topic,
            font_size=48, color=RGBColor(0xFF, 0xFF, 0xFF), bold=True,
        )
        self._add_textbox(
            slide, 1.5, 3.2, 10, 0.6,
            f"共 {deck.total_slides} 页课件",
            font_size=20, color=self.theme.accent,
        )
        self._add_textbox(
            slide, 1.5, 4.0, 10, 0.5,
            "EduAgent AI 驱动生成",
            font_size=14, color=self.theme.text_secondary,
        )

    def _render_toc(self, prs: Presentation, deck: PPTDeck) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        self._add_bg(slide, self.theme.bg)

        self._add_textbox(
            slide, 1.0, 0.5, 5, 0.6, "目录",
            font_size=32, color=self.theme.primary, bold=True,
        )
        self._add_shape(slide, 1.0, 1.1, 1.5, 0.04, fill_color=self.theme.accent)

        for i, s in enumerate(deck.slides):
            col = i % 2
            row = i // 2
            x = 1.0 + col * 6.2
            y = 1.5 + row * 0.65

            num_str = f"{s.slide_number:02d}"
            self._add_textbox(
                slide, x, y, 0.6, 0.4, num_str,
                font_size=18, color=self.theme.accent, bold=True,
            )
            self._add_textbox(
                slide, x + 0.7, y, 5, 0.4, s.title,
                font_size=15, color=self.theme.text, bold=True,
            )

        self._slide_number(slide, 2)

    def _render_content_slide(self, prs: Presentation, slide_data: PPTSlide, deck: PPTDeck) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        self._add_bg(slide, self.theme.bg)

        # 顶部标题栏
        self._add_shape(slide, 0, 0, 13.333, 1.2, fill_color=self.theme.primary)
        self._add_textbox(
            slide, 0.8, 0.2, 11, 0.8, slide_data.title,
            font_size=28, color=RGBColor(0xFF, 0xFF, 0xFF), bold=True,
        )

        # 内容区域
        content_items = slide_data.content[:8]  # 最多8条要点
        if content_items:
            tf = self._add_textbox(
                slide, 1.0, 1.6, 11, 5.0, "",
                font_size=18, color=self.theme.text,
            )
            self._add_bullet_list(tf, content_items, font_size=18, color=self.theme.text)

        # 演讲备注
        if slide_data.notes:
            self._add_shape(slide, 0.8, 6.2, 11.7, 0.8, fill_color=self.theme.accent_light)
            self._add_textbox(
                slide, 1.0, 6.3, 11.3, 0.6,
                f"备注: {slide_data.notes}",
                font_size=12, color=self.theme.text_secondary,
            )

        self._slide_number(slide, slide_data.slide_number + 2)  # +2 for cover+toc

    def _render_end(self, prs: Presentation, deck: PPTDeck) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        self._add_bg(slide, self.theme.primary_dark)

        self._add_textbox(
            slide, 1.5, 2.5, 10, 1.0, "谢谢",
            font_size=48, color=RGBColor(0xFF, 0xFF, 0xFF), bold=True,
            align=PP_ALIGN.CENTER,
        )
        self._add_textbox(
            slide, 1.5, 3.8, 10, 0.6, deck.topic,
            font_size=20, color=self.theme.accent,
            align=PP_ALIGN.CENTER,
        )
        self._add_textbox(
            slide, 1.5, 4.8, 10, 0.5,
            "EduAgent AI 驱动生成",
            font_size=14, color=self.theme.text_secondary,
            align=PP_ALIGN.CENTER,
        )
