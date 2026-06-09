"""HTMLPPTRenderer — 将 PPTDeck 渲染为可交互 HTML 演示文稿

基于 html-ppt-skill (https://github.com/lewislulu/html-ppt-skill)
所有 CSS/JS 资源内联到 HTML 中，确保文件独立可运行。
"""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from schemas.profile import PPTDeck

logger = logging.getLogger(__name__)

# 目录常量
_STATIC_DIR = Path(__file__).parent / "static"
_TEMPLATES_DIR = Path(__file__).parent / "templates"

# 精选主题列表（教育场景）
AVAILABLE_THEMES: dict[str, str] = {
    "corporate-clean": "企业商务",
    "academic-paper": "学术论文",
    "tokyo-night": "东京暗夜",
    "blueprint": "蓝图工程",
    "soft-pastel": "柔和马卡龙",
    "xiaohongshu-white": "小红书白底",
    "minimal-white": "极简白",
    "dracula": "Dracula暗色",
}

# 布局映射：根据 slide 在 deck 中的位置自动选择布局
# 首页 → cover, 末页 → end, 中间 → content
_LAYOUT_RULES = {
    "cover": "cover",
    "toc": "toc",
    "content": "content",
    "end": "end",
}


class HTMLPPTRenderer:
    """将 PPTDeck 渲染为完整 HTML 演示文稿

    所有 CSS/JS 资源内联到 HTML 中，输出文件可直接在浏览器打开。
    支持键盘导航、主题切换、演讲者模式等 html-ppt-skill 全部特性。
    """

    def __init__(
        self,
        theme: str = "corporate-clean",
        with_presenter: bool = False,
    ) -> None:
        if theme not in AVAILABLE_THEMES:
            logger.warning("未知主题 %s，回退到 corporate-clean", theme)
            theme = "corporate-clean"
        self.theme = theme
        self.with_presenter = with_presenter
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=False,  # HTML 模板中包含 CSS/JS，不转义
        )

    def render(self, deck: PPTDeck) -> str:
        """渲染 PPTDeck 为完整 HTML 字符串"""
        # 1. 读取并内联静态资源
        base_css = self._read_static("base.css")
        theme_css = self._read_static(f"themes/{self.theme}.css")
        fonts_css = self._read_static("fonts.css")
        anim_css = self._read_static("animations/animations.css")
        runtime_js = self._read_static("runtime.js")

        # 2. 为每个 slide 分配布局
        slides_with_layout = self._assign_layouts(deck)

        # 3. Jinja2 渲染
        tmpl = self._jinja_env.get_template("deck.html.j2")
        html = tmpl.render(
            deck=deck,
            slides_with_layout=slides_with_layout,
            base_css=base_css,
            theme_css=theme_css,
            fonts_css=fonts_css,
            anim_css=anim_css,
            runtime_js=runtime_js,
            with_presenter=self.with_presenter,
            theme_name=self.theme,
        )

        logger.info(
            "HTML PPT 渲染完成: topic=%s, slides=%d, theme=%s, size=%d bytes",
            deck.topic, deck.total_slides, self.theme, len(html.encode("utf-8")),
        )
        return html

    def _read_static(self, relative_path: str) -> str:
        """读取静态资源文件内容"""
        file_path = _STATIC_DIR / relative_path
        try:
            return file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning("静态资源未找到: %s", file_path)
            return ""

    def _assign_layouts(self, deck: PPTDeck) -> list[dict]:
        """为每个 slide 分配布局类型和元数据"""
        result = []
        for i, slide in enumerate(deck.slides):
            if i == 0:
                layout = "cover"
            elif i == deck.total_slides - 1:
                layout = "end"
            else:
                layout = "content"

            result.append({
                "slide": slide,
                "layout": layout,
                "index": i,
                "is_first": i == 0,
                "is_last": i == deck.total_slides - 1,
            })
        return result
