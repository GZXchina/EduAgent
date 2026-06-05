"""
EduAgent 项目讲解 PPT 生成脚本
生成一份专业的项目介绍演示文稿，适用于技术分享、项目汇报等场景。
"""

import logging
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt, Emu

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 配色方案
# ---------------------------------------------------------------------------
PRIMARY = RGBColor(0x1A, 0x56, 0xDB)       # 主色 - 深蓝
PRIMARY_DARK = RGBColor(0x0F, 0x3B, 0x99)  # 深蓝
ACCENT = RGBColor(0x10, 0xB9, 0x81)        # 强调色 - 翠绿
ACCENT_LIGHT = RGBColor(0xD1, 0xFA, 0xE5)  # 浅绿背景
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0x1F, 0x29, 0x37)
GRAY = RGBColor(0x6B, 0x72, 0x80)
LIGHT_GRAY = RGBColor(0xF3, 0xF4, 0xF6)
DARK_BG = RGBColor(0x0F, 0x17, 0x2A)
ORANGE = RGBColor(0xF5, 0x9E, 0x0B)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _add_bg(slide, color):
    """填充幻灯片背景色"""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_textbox(slide, left, top, width, height, text, font_size=18,
                 color=BLACK, bold=False, align=PP_ALIGN.LEFT, font_name="Microsoft YaHei"):
    """添加文本框"""
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    p.alignment = align
    return tf


def _add_shape(slide, shape_type, left, top, width, height, fill_color=None, line_color=None):
    """添加形状"""
    shape = slide.shapes.add_shape(shape_type, Inches(left), Inches(top), Inches(width), Inches(height))
    if fill_color:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_color
    else:
        shape.fill.background()
    if line_color:
        shape.line.color.rgb = line_color
    else:
        shape.line.fill.background()
    return shape


def _add_bullet_list(tf, items, font_size=16, color=BLACK, spacing=Pt(6)):
    """向已有文本框添加项目符号列表"""
    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = f"  {item}"
        p.font.size = Pt(font_size)
        p.font.color.rgb = color
        p.font.name = "Microsoft YaHei"
        p.space_after = spacing
        p.level = 0


def _section_header(slide, number, title, subtitle=""):
    """章节标题页通用布局"""
    _add_bg(slide, PRIMARY)
    # 左侧色条
    _add_shape(slide, 1, 0, 0, 0.3, 7.5, fill_color=ACCENT)
    _add_textbox(slide, 1.8, 2.2, 10, 0.8, f"0{number}", font_size=48, color=ACCENT, bold=True)
    _add_textbox(slide, 1.8, 3.2, 10, 1.0, title, font_size=36, color=WHITE, bold=True)
    if subtitle:
        _add_textbox(slide, 1.8, 4.3, 10, 0.6, subtitle, font_size=18, color=RGBColor(0x93, 0xA3, 0xBA))


def _slide_number(slide, num):
    """右下角页码"""
    _add_textbox(slide, 12.3, 7.0, 0.8, 0.4, str(num), font_size=10, color=GRAY, align=PP_ALIGN.RIGHT)


def _card(slide, left, top, width, height, title, items, title_color=PRIMARY, icon=""):
    """信息卡片"""
    # 卡片背景
    card = _add_shape(slide, 1, left, top, width, height, fill_color=WHITE, line_color=RGBColor(0xE5, 0xE7, 0xEB))
    card.shadow.inherit = False
    # 标题
    header = _add_shape(slide, 1, left, top, width, 0.5, fill_color=PRIMARY)
    _add_textbox(slide, left + 0.2, top + 0.05, width - 0.4, 0.4,
                 f"{icon} {title}", font_size=14, color=WHITE, bold=True)
    # 内容
    tf = _add_textbox(slide, left + 0.2, top + 0.6, width - 0.4, height - 0.7,
                      "", font_size=12, color=BLACK)
    _add_bullet_list(tf, items, font_size=12, color=BLACK, spacing=Pt(4))
    return tf


# ===========================================================================
# Slide 1: 封面
# ===========================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
_add_bg(slide, DARK_BG)

# 装饰线
_add_shape(slide, 1, 1.5, 3.0, 0.8, 0.06, fill_color=ACCENT)
_add_shape(slide, 1, 1.5, 5.5, 0.8, 0.03, fill_color=PRIMARY)

_add_textbox(slide, 1.5, 1.5, 10, 0.8, "EduAgent", font_size=56, color=WHITE, bold=True)
_add_textbox(slide, 1.5, 2.5, 10, 0.6, "AI 驱动的个性化学习智能体平台", font_size=24, color=ACCENT)
_add_textbox(slide, 1.5, 3.4, 10, 0.5,
             "基于 FastAPI + Vue3 + LangGraph 的多智能体教育系统",
             font_size=16, color=RGBColor(0x93, 0xA3, 0xBA))

# 底部信息
_add_textbox(slide, 1.5, 5.5, 10, 0.4, "高校个性化学习场景  |  多智能体协同  |  RAG 知识库  |  语音交互", font_size=14, color=GRAY)
_add_textbox(slide, 1.5, 6.3, 10, 0.4, "2026年6月", font_size=12, color=GRAY)

# 右侧装饰
_add_shape(slide, 1, 9.5, 0.5, 4.0, 0.04, fill_color=ACCENT)
_add_shape(slide, 1, 10.0, 0.5, 4.0, 0.04, fill_color=PRIMARY)


# ===========================================================================
# Slide 2: 目录
# ===========================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])
_add_bg(slide, WHITE)

_add_textbox(slide, 1.0, 0.5, 5, 0.6, "目录", font_size=32, color=PRIMARY, bold=True)
_add_shape(slide, 1, 1.0, 1.3, 1.5, 0.04, fill_color=ACCENT)

toc_items = [
    ("01", "项目概述", "背景、目标与核心价值"),
    ("02", "技术栈总览", "前后端技术选型与基础设施"),
    ("03", "系统架构", "整体架构设计与数据流"),
    ("04", "后端架构", "FastAPI 分层设计与核心模块"),
    ("05", "前端架构", "Vue3 组件化设计与交互体验"),
    ("06", "多智能体系统", "Agent 协作与双通道策略"),
    ("07", "LangGraph 工作流", "工作流编排与评估闭环"),
    ("08", "RAG 知识库", "文档解析、向量检索与问答"),
    ("09", "语音能力", "讯飞 ASR / TTS 集成"),
    ("10", "用户认证", "JWT 认证与权限管理"),
    ("11", "项目阶段", "十一个阶段的工程化迭代"),
    ("12", "部署与运维", "Docker 容器化与一键部署"),
    ("13", "总结展望", "项目亮点与未来规划"),
]

for i, (num, title, desc) in enumerate(toc_items):
    col = i % 2
    row = i // 2
    x = 1.0 + col * 6.2
    y = 1.8 + row * 0.75

    _add_textbox(slide, x, y, 0.6, 0.4, num, font_size=20, color=ACCENT, bold=True)
    _add_textbox(slide, x + 0.7, y, 5, 0.35, title, font_size=16, color=BLACK, bold=True)
    _add_textbox(slide, x + 0.7, y + 0.35, 5, 0.3, desc, font_size=11, color=GRAY)


# ===========================================================================
# Slide 3: 项目概述
# ===========================================================================
_section_header(slide := prs.slides.add_slide(prs.slide_layouts[6]), 1, "项目概述", "背景、目标与核心价值")
_slide_number(slide, 3)

slide = prs.slides.add_slide(prs.slide_layouts[6])
_add_bg(slide, WHITE)
_add_textbox(slide, 0.8, 0.4, 5, 0.5, "项目概述", font_size=28, color=PRIMARY, bold=True)
_add_shape(slide, 1, 0.8, 0.9, 2.5, 0.04, fill_color=ACCENT)

# 三列卡片
_card(slide, 0.8, 1.3, 3.8, 2.6, "项目背景", [
    "面向高校学生的个性化学习需求",
    "传统教学难以满足个体差异",
    "大模型技术为教育带来新可能",
    "需要智能化的学习资源生成与评估",
], icon="")

_card(slide, 5.0, 1.3, 3.8, 2.6, "核心目标", [
    "多智能体协同编排学习流程",
    "RAG + 大模型双通道知识服务",
    "从学习画像到资源生成的全链路",
    "语音交互提升学习体验",
], icon="")

_card(slide, 9.2, 1.3, 3.8, 2.6, "核心价值", [
    "个性化：基于学生画像定制学习路径",
    "智能化：AI 自动生成课件、题库、思维导图",
    "闭环化：评估反馈驱动学习路径动态调整",
    "工程化：Docker 一键部署，本地开发友好",
], icon="")

# 底部关键数据
stats = [
    ("10+", "智能体 Agent"),
    ("11", "工程阶段"),
    ("5", "前端功能模块"),
    ("6+", "API 端点"),
]
for i, (num, label) in enumerate(stats):
    x = 1.5 + i * 3.0
    _add_textbox(slide, x, 4.5, 2.5, 0.5, num, font_size=36, color=ACCENT, bold=True, align=PP_ALIGN.CENTER)
    _add_textbox(slide, x, 5.1, 2.5, 0.4, label, font_size=14, color=GRAY, align=PP_ALIGN.CENTER)

_slide_number(slide, 4)


# ===========================================================================
# Slide 5: 技术栈总览
# ===========================================================================
_section_header(slide := prs.slides.add_slide(prs.slide_layouts[6]), 2, "技术栈总览", "前后端技术选型与基础设施")
_slide_number(slide, 5)

slide = prs.slides.add_slide(prs.slide_layouts[6])
_add_bg(slide, WHITE)
_add_textbox(slide, 0.8, 0.4, 5, 0.5, "技术栈总览", font_size=28, color=PRIMARY, bold=True)
_add_shape(slide, 1, 0.8, 0.9, 3.5, 0.04, fill_color=ACCENT)

tech_data = [
    ("后端", PRIMARY, [
        "FastAPI - 高性能异步 Web 框架",
        "SQLAlchemy 2.0 + PostgreSQL",
        "Redis 缓存与会话管理",
        "LangGraph 工作流编排",
        "LangChain / ChromaDB / Sentence Transformers",
        "bcrypt + python-jose (JWT 认证)",
    ]),
    ("前端", ACCENT, [
        "Vue 3.5 + TypeScript",
        "Vite 8.0 构建工具",
        "TailwindCSS 4.3 样式框架",
        "Vue Router 4 路由管理",
        "marked + highlight.js 内容渲染",
        "mermaid 图表渲染",
    ]),
    ("AI / ML", ORANGE, [
        "讯飞星火大模型 API",
        "Sentence Transformers 嵌入模型",
        "ChromaDB 向量数据库",
        "LangChain RAG 检索链",
        "讯飞 ASR 语音识别",
        "讯飞 TTS 语音合成",
    ]),
    ("基础设施", GRAY, [
        "Docker + Docker Compose",
        "Nginx 反向代理",
        "PostgreSQL 数据库",
        "Redis 缓存",
        "Windows / Linux 双平台支持",
        "一键启动脚本",
    ]),
]

for i, (title, color, items) in enumerate(tech_data):
    x = 0.8 + i * 3.15
    _card(slide, x, 1.3, 2.95, 3.4, title, items, title_color=color)

# 底部认证技术栈
_card(slide, 0.8, 5.0, 6.0, 2.0, "新增认证技术栈", [
    "vue-router@4 - SPA 路由管理与守卫",
    "bcrypt>=4.0.0 - 密码哈希",
    "python-jose[cryptography]>=3.3.0 - JWT 令牌",
], title_color=PRIMARY)

_card(slide, 7.2, 5.0, 5.5, 2.0, "开发工具", [
    "uvicorn 热重载开发服务器",
    "Vite HMR 热模块替换",
    "Trae IDE 智能编码助手",
    "Git 版本控制",
], title_color=ACCENT)

_slide_number(slide, 6)


# ===========================================================================
# Slide 7: 系统架构
# ===========================================================================
_section_header(slide := prs.slides.add_slide(prs.slide_layouts[6]), 3, "系统架构", "整体架构设计与数据流")
_slide_number(slide, 7)

slide = prs.slides.add_slide(prs.slide_layouts[6])
_add_bg(slide, WHITE)
_add_textbox(slide, 0.8, 0.4, 5, 0.5, "系统架构", font_size=28, color=PRIMARY, bold=True)
_add_shape(slide, 1, 0.8, 0.9, 2.0, 0.04, fill_color=ACCENT)

# 架构分层
layers = [
    ("前端层", ACCENT, 0.8, "Vue3 + Vite + TailwindCSS\n五大功能模块\nVue Router 路由守卫"),
    ("API 网关层", PRIMARY, 2.6, "FastAPI RESTful API\nJWT 认证中间件\nCORS 跨域处理"),
    ("业务逻辑层", RGBColor(0x7C, 0x3A, 0xED), 4.4, "多智能体 Agent\nLangGraph 工作流\nRAG 知识检索\n评估服务"),
    ("基础设施层", RGBColor(0x37, 0x41, 0x51), 6.2, "PostgreSQL + Redis\nChromaDB 向量库\nDocker + Nginx\n讯飞 API 网关"),
]

for title, color, y, desc in layers:
    _add_shape(slide, 1, 0.8, y, 12.0, 1.2, fill_color=color)
    _add_textbox(slide, 1.0, y + 0.1, 2.5, 0.4, title, font_size=18, color=WHITE, bold=True)
    _add_textbox(slide, 3.5, y + 0.1, 9.0, 1.0, desc, font_size=13, color=WHITE)

# 右侧外部集成
ext_items = [
    "讯飞星火大模型",
    "讯飞 ASR 语音识别",
    "讯飞 TTS 语音合成",
]
for i, item in enumerate(ext_items):
    _add_textbox(slide, 10.5, 1.0 + i * 0.5, 2.5, 0.4, item, font_size=11, color=ORANGE, bold=True)

_slide_number(slide, 8)


# ===========================================================================
# Slide 9: 后端架构
# ===========================================================================
_section_header(slide := prs.slides.add_slide(prs.slide_layouts[6]), 4, "后端架构", "FastAPI 分层设计与核心模块")
_slide_number(slide, 9)

slide = prs.slides.add_slide(prs.slide_layouts[6])
_add_bg(slide, WHITE)
_add_textbox(slide, 0.8, 0.4, 5, 0.5, "后端架构", font_size=28, color=PRIMARY, bold=True)
_add_shape(slide, 1, 0.8, 0.9, 2.5, 0.04, fill_color=ACCENT)

_card(slide, 0.8, 1.3, 3.8, 2.8, "应用入口与配置", [
    "backend/main.py - 生命周期管理",
    "backend/settings.py - Pydantic Settings",
    "首次启动自动创建管理员账号",
    "CORS 中间件 + 路由注册",
], title_color=PRIMARY)

_card(slide, 5.0, 1.3, 3.8, 2.8, "核心基础设施", [
    "backend/core/logging_config.py",
    "backend/core/redis_client.py",
    "backend/core/auth.py - JWT + bcrypt",
    "backend/core/deps.py - 依赖注入",
], title_color=PRIMARY)

_card(slide, 9.2, 1.3, 3.8, 2.8, "数据访问层", [
    "database/session.py - SQLAlchemy 引擎",
    "database/models.py - ORM 模型",
    "database/repository.py - 仓储模式",
    "User 模型 + 角色权限",
], title_color=PRIMARY)

_card(slide, 0.8, 4.5, 3.8, 2.5, "路由与接口", [
    "api/routes/chat.py - 对话接口",
    "api/routes/profile.py - 画像接口",
    "api/routes/workflow.py - 工作流接口",
    "api/routes/auth.py - 认证接口",
], title_color=PRIMARY)

_card(slide, 5.0, 4.5, 3.8, 2.5, "工作流编排", [
    "workflows/graph.py - LangGraph 状态机",
    "workflows/state.py - 工作流状态定义",
    "多 Agent 并行与串行调度",
    "评估回流机制",
], title_color=PRIMARY)

_card(slide, 9.2, 4.5, 3.8, 2.5, "外部集成", [
    "backend/integrations/spark/ - 星火大模型",
    "backend/integrations/asr/ - 语音识别",
    "backend/integrations/tts/ - 语音合成",
    "WebSocket 鉴权与流式处理",
], title_color=PRIMARY)

_slide_number(slide, 10)


# ===========================================================================
# Slide 11: 前端架构
# ===========================================================================
_section_header(slide := prs.slides.add_slide(prs.slide_layouts[6]), 5, "前端架构", "Vue3 组件化设计与交互体验")
_slide_number(slide, 11)

slide = prs.slides.add_slide(prs.slide_layouts[6])
_add_bg(slide, WHITE)
_add_textbox(slide, 0.8, 0.4, 5, 0.5, "前端架构", font_size=28, color=PRIMARY, bold=True)
_add_shape(slide, 1, 0.8, 0.9, 2.5, 0.04, fill_color=ACCENT)

_card(slide, 0.8, 1.3, 3.8, 2.5, "路由与认证", [
    "Vue Router 4 - SPA 路由管理",
    "全局 beforeEach 守卫",
    "useAuth composable 状态管理",
    "JWT 持久化到 localStorage",
    "管理员 / 普通用户权限控制",
], title_color=ACCENT)

_card(slide, 5.0, 1.3, 3.8, 2.5, "核心功能模块", [
    "ChatLearning - AI 对话学习",
    "PersonalizedLearning - 个性化中心",
    "ResourceGenerator - 资源生成",
    "EvaluationCenter - 学习评估",
    "VoiceLearning - 语音交互",
], title_color=ACCENT)

_card(slide, 9.2, 1.3, 3.8, 2.5, "页面与布局", [
    "LoginPage - 登录/注册页",
    "HomePage - 主功能页",
    "AdminPanel - 用户管理面板",
    "App.vue - 路由驱动布局壳",
    "侧边栏 + 顶栏 + 内容区",
], title_color=ACCENT)

_card(slide, 0.8, 4.2, 6.0, 2.8, "交互体验", [
    "流式打字机效果 - 模拟实时对话",
    "骨架屏加载 - 优化等待体验",
    "平滑动画过渡",
    "暗色代码块 + 语法高亮 (highlight.js)",
    "Mermaid 图表渲染",
    "响应式设计 - 适配桌面/平板/移动端",
], title_color=ACCENT)

_card(slide, 7.2, 4.2, 5.5, 2.8, "技术特点", [
    "Composition API + TypeScript",
    "组合式函数 (composables) 复用逻辑",
    "Vite 代理解决跨域",
    "marked 渲染 Markdown",
    "authFetch 自动附加 Bearer Token",
    "TailwindCSS 原子化样式",
], title_color=ACCENT)

_slide_number(slide, 12)


# ===========================================================================
# Slide 13: 多智能体系统
# ===========================================================================
_section_header(slide := prs.slides.add_slide(prs.slide_layouts[6]), 6, "多智能体系统", "Agent 协作与双通道策略")
_slide_number(slide, 13)

slide = prs.slides.add_slide(prs.slide_layouts[6])
_add_bg(slide, WHITE)
_add_textbox(slide, 0.8, 0.4, 5, 0.5, "多智能体系统", font_size=28, color=PRIMARY, bold=True)
_add_shape(slide, 1, 0.8, 0.9, 2.5, 0.04, fill_color=ACCENT)

agents = [
    ("ProfileAgent", "学习画像", "分析学生知识水平、学习风格、薄弱点，生成结构化画像", PRIMARY),
    ("PlannerAgent", "学习规划", "基于画像制定个性化学习路径与阶段目标", PRIMARY),
    ("KnowledgeAgent", "知识拆解", "结合 RAG 与星火生成知识树，结构化拆解知识点", PRIMARY),
    ("PPTAgent", "课件生成", "自动生成 Markdown 课件，支持三级难度和四类学习风格", ACCENT),
    ("QuizAgent", "题库生成", "自动生成练习题、测试题，支持多种题型", ACCENT),
    ("CodeAgent", "代码生成", "生成编程练习代码与示例", ACCENT),
    ("MindmapAgent", "思维导图", "将知识结构可视化为思维导图", ACCENT),
    ("VideoScriptAgent", "视频脚本", "生成教学视频脚本与解说词", ACCENT),
    ("SafetyAgent", "安全审核", "审核生成内容的安全性、合规性", ORANGE),
    ("EvaluationAgent", "学习评估", "评估学习效果，驱动画像动态更新", ORANGE),
]

for i, (name, cn_name, desc, color) in enumerate(agents):
    col = i % 2
    row = i // 2
    x = 0.8 + col * 6.2
    y = 1.2 + row * 1.15

    # Agent 卡片
    _add_shape(slide, 1, x, y, 5.8, 0.95, fill_color=LIGHT_GRAY, line_color=color)
    _add_textbox(slide, x + 0.2, y + 0.05, 2.5, 0.35, name, font_size=15, color=color, bold=True)
    _add_textbox(slide, x + 2.8, y + 0.05, 2.8, 0.35, cn_name, font_size=12, color=GRAY)
    _add_textbox(slide, x + 0.2, y + 0.45, 5.4, 0.4, desc, font_size=12, color=BLACK)

# 底部双通道说明
_add_textbox(slide, 0.8, 6.3, 12, 0.4, "双通道策略：星火大模型生成 → 失败自动降级为规则引擎兜底，保证系统在不可用环境下仍稳定运行", font_size=13, color=ORANGE, bold=True)
_add_textbox(slide, 0.8, 6.7, 12, 0.4, "统一基类 BaseAgent：所有 Agent 继承统一抽象基类，实现标准化的 run() 接口", font_size=13, color=GRAY)

_slide_number(slide, 14)


# ===========================================================================
# Slide 15: LangGraph 工作流
# ===========================================================================
_section_header(slide := prs.slides.add_slide(prs.slide_layouts[6]), 7, "LangGraph 工作流", "工作流编排与评估闭环")
_slide_number(slide, 15)

slide = prs.slides.add_slide(prs.slide_layouts[6])
_add_bg(slide, WHITE)
_add_textbox(slide, 0.8, 0.4, 5, 0.5, "LangGraph 工作流", font_size=28, color=PRIMARY, bold=True)
_add_shape(slide, 1, 0.8, 0.9, 2.5, 0.04, fill_color=ACCENT)

# 工作流步骤
steps = [
    ("1", "画像分析", "ProfileAgent 分析学生画像", PRIMARY),
    ("2", "学习规划", "PlannerAgent 制定学习路径", PRIMARY),
    ("3", "知识拆解", "KnowledgeAgent 拆解知识点", PRIMARY),
    ("4", "并行生成", "PPT/题库/代码/思维导图/视频脚本", ACCENT),
    ("5", "安全审核", "SafetyAgent 审核内容合规性", ORANGE),
    ("6", "学习评估", "EvaluationAgent 评估学习效果", ORANGE),
    ("7", "回流优化", "评估不达标 → 回流画像 Agent 重新规划", RGBColor(0xEF, 0x44, 0x44)),
]

for i, (num, title, desc, color) in enumerate(steps):
    x = 0.8 + i * 1.8
    # 圆形节点
    shape = _add_shape(slide, 9, x + 0.4, 1.3, 1.0, 1.0, fill_color=color)
    tf = shape.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = num
    p.font.size = Pt(24)
    p.font.color.rgb = WHITE
    p.font.bold = True
    p.alignment = PP_ALIGN.CENTER
    tf.paragraphs[0].space_before = Pt(0)

    _add_textbox(slide, x, 2.5, 1.8, 0.35, title, font_size=13, color=BLACK, bold=True, align=PP_ALIGN.CENTER)
    _add_textbox(slide, x, 2.85, 1.8, 0.5, desc, font_size=10, color=GRAY, align=PP_ALIGN.CENTER)

    # 箭头
    if i < len(steps) - 1:
        _add_shape(slide, 3, x + 1.8, 1.5, 0.55, 0.03, fill_color=GRAY)

# 回流箭头（底部）
_add_shape(slide, 3, 11.5, 3.8, 0.55, 0.03, fill_color=RGBColor(0xEF, 0x44, 0x44))
_add_textbox(slide, 9.0, 3.6, 3.5, 0.3, "← 回流（最多2次）", font_size=10, color=RGBColor(0xEF, 0x44, 0x44), align=PP_ALIGN.RIGHT)

# 特性说明
features = [
    "并行与串行混合：知识拆解完成后，资源生成 Agent 并行执行",
    "评估回流机制：评估不达标自动回流画像 Agent，最多两次，动态调整路径",
    "状态管理：workflows/state.py 定义完整工作流状态，节点间数据传递标准化",
    "星火 + 规则双通道：大模型不可用时自动降级，保证功能可用性",
]
for i, f in enumerate(features):
    _add_textbox(slide, 0.8, 4.5 + i * 0.5, 12, 0.4, f"  {f}", font_size=14, color=BLACK)

_slide_number(slide, 16)


# ===========================================================================
# Slide 17: RAG 知识库
# ===========================================================================
_section_header(slide := prs.slides.add_slide(prs.slide_layouts[6]), 8, "RAG 知识库", "文档解析、向量检索与智能问答")
_slide_number(slide, 17)

slide = prs.slides.add_slide(prs.slide_layouts[6])
_add_bg(slide, WHITE)
_add_textbox(slide, 0.8, 0.4, 5, 0.5, "RAG 知识库", font_size=28, color=PRIMARY, bold=True)
_add_shape(slide, 1, 0.8, 0.9, 2.5, 0.04, fill_color=ACCENT)

_card(slide, 0.8, 1.3, 3.8, 3.0, "文档处理流程", [
    "文档加载：支持 PDF、TXT、Markdown",
    "文本切片：智能分块，保持语义完整",
    "嵌入生成：Sentence Transformers",
    "向量存储：ChromaDB",
    "相似检索：余弦相似度 Top-K",
])

_card(slide, 5.0, 1.3, 3.8, 3.0, "检索增强生成", [
    "用户提问 → 向量化",
    "向量检索 → 召回相关文档片段",
    "拼接 Prompt → 发送给大模型",
    "大模型结合上下文生成回答",
    "支持多轮对话上下文",
])

_card(slide, 9.2, 1.3, 3.8, 3.0, "知识库管理", [
    "增量入库：支持新增文档",
    "批量导入：脚本化批量处理",
    "知识树构建：结构化知识拆解",
    "与工作流无缝集成",
    "支撑知识拆解 Agent",
])

# 底部架构图
_add_shape(slide, 1, 0.8, 4.8, 12.0, 2.0, fill_color=LIGHT_GRAY)
_add_textbox(slide, 1.0, 4.9, 12, 0.3, "RAG 数据流：文档上传 → 解析切片 → 嵌入向量化 → ChromaDB 存储 → 相似检索 → 上下文增强生成", font_size=13, color=PRIMARY, bold=True, align=PP_ALIGN.CENTER)

modules = [
    ("文档解析", PRIMARY),
    ("文本切片", PRIMARY),
    ("嵌入生成", ACCENT),
    ("向量存储", ACCENT),
    ("相似检索", ORANGE),
    ("上下文生成", ORANGE),
]
for i, (name, color) in enumerate(modules):
    x = 1.2 + i * 2.0
    _add_shape(slide, 1, x, 5.5, 1.8, 0.5, fill_color=color)
    _add_textbox(slide, x, 5.55, 1.8, 0.4, name, font_size=11, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    if i < len(modules) - 1:
        _add_textbox(slide, x + 1.8, 5.55, 0.2, 0.4, "→", font_size=16, color=GRAY, align=PP_ALIGN.CENTER)

_slide_number(slide, 18)


# ===========================================================================
# Slide 19: 语音能力
# ===========================================================================
_section_header(slide := prs.slides.add_slide(prs.slide_layouts[6]), 9, "语音能力", "讯飞 ASR / TTS 集成")
_slide_number(slide, 19)

slide = prs.slides.add_slide(prs.slide_layouts[6])
_add_bg(slide, WHITE)
_add_textbox(slide, 0.8, 0.4, 5, 0.5, "语音能力", font_size=28, color=PRIMARY, bold=True)
_add_shape(slide, 1, 0.8, 0.9, 2.5, 0.04, fill_color=ACCENT)

_card(slide, 0.8, 1.3, 5.8, 3.0, "ASR 语音识别", [
    "WebSocket 实时音频流传输",
    "支持 PCM / WAV 音频格式",
    "讯飞 WebSocket 鉴权（HMAC-SHA256）",
    "API 端点：POST /api/voice/asr",
    "返回识别文本与置信度",
    "前端录音 → 后端转发 → 讯飞识别 → 返回结果",
], title_color=PRIMARY)

_card(slide, 7.0, 1.3, 5.8, 3.0, "TTS 语音合成", [
    "HTTP POST 请求音频合成",
    "支持多种音色（xiaoyan、xiaoqi 等）",
    "MP3 音频输出（aue=lame）",
    "sfl=1 参数确保流式音频完整",
    "API 端点：POST /api/voice/tts",
    "前端播放 → 后端合成 → 返回音频流",
], title_color=ACCENT)

_card(slide, 0.8, 4.8, 12.0, 2.2, "语音服务封装", [
    "backend/integrations/asr/client.py - ASR 客户端",
    "backend/integrations/tts/client.py - TTS 客户端",
    "backend/integrations/voice/auth.py - WebSocket 鉴权",
    "VoiceLearning 前端组件 - 录音 + 播放 UI",
    "语音状态查询：GET /api/voice/status",
    "未配置时优雅降级，不阻断主流程",
], title_color=ORANGE)

_slide_number(slide, 20)


# ===========================================================================
# Slide 21: 用户认证
# ===========================================================================
_section_header(slide := prs.slides.add_slide(prs.slide_layouts[6]), 10, "用户认证与权限管理", "JWT 认证 + 角色权限控制")
_slide_number(slide, 21)

slide = prs.slides.add_slide(prs.slide_layouts[6])
_add_bg(slide, WHITE)
_add_textbox(slide, 0.8, 0.4, 5, 0.5, "用户认证与权限管理", font_size=28, color=PRIMARY, bold=True)
_add_shape(slide, 1, 0.8, 0.9, 2.5, 0.04, fill_color=ACCENT)

_card(slide, 0.8, 1.3, 3.8, 3.0, "后端认证体系", [
    "JWT Bearer Token（HS256）",
    "bcrypt 密码哈希（不可逆）",
    "Token 24 小时过期",
    "get_current_user 依赖注入",
    "require_admin 权限校验",
    "预设管理员自动创建",
], title_color=PRIMARY)

_card(slide, 5.0, 1.3, 3.8, 3.0, "API 端点", [
    "POST /api/auth/login - 登录",
    "POST /api/auth/register - 注册",
    "GET /api/auth/me - 获取当前用户",
    "GET /api/auth/users - 用户列表(管理员)",
    "PUT /api/auth/users/{id}/role - 修改角色",
    "DELETE /api/auth/users/{id} - 禁用用户",
], title_color=PRIMARY)

_card(slide, 9.2, 1.3, 3.8, 3.0, "前端认证体系", [
    "useAuth composable 全局状态",
    "JWT + 用户信息 localStorage 持久化",
    "authFetch 自动附加 Token",
    "Vue Router 全局路由守卫",
    "LoginPage 登录/注册切换",
    "AdminPanel 用户管理面板",
], title_color=ACCENT)

# 角色对比
_add_shape(slide, 1, 0.8, 4.8, 5.8, 2.5, fill_color=LIGHT_GRAY)
_add_textbox(slide, 1.0, 4.9, 5.4, 0.4, "角色权限对比", font_size=16, color=PRIMARY, bold=True, align=PP_ALIGN.CENTER)

role_data = [
    ("管理员 (admin)", ACCENT, [
        "访问全部功能模块",
        "用户管理面板",
        "修改用户角色",
        "禁用/启用用户",
    ]),
    ("普通用户 (user)", PRIMARY, [
        "对话学习、个性化学习",
        "资源生成、语音学习",
        "学习评估",
        "自行注册账号",
    ]),
]
for i, (role, color, perms) in enumerate(role_data):
    x = 1.2 + i * 3.0
    _add_textbox(slide, x, 5.4, 2.8, 0.3, role, font_size=14, color=color, bold=True, align=PP_ALIGN.CENTER)
    for j, perm in enumerate(perms):
        _add_textbox(slide, x, 5.8 + j * 0.35, 2.8, 0.3, f"  {perm}", font_size=12, color=BLACK)

_slide_number(slide, 22)


# ===========================================================================
# Slide 23: 项目阶段
# ===========================================================================
_section_header(slide := prs.slides.add_slide(prs.slide_layouts[6]), 11, "项目阶段", "十一个阶段的工程化迭代")
_slide_number(slide, 23)

slide = prs.slides.add_slide(prs.slide_layouts[6])
_add_bg(slide, WHITE)
_add_textbox(slide, 0.8, 0.4, 5, 0.5, "项目阶段", font_size=28, color=PRIMARY, bold=True)
_add_shape(slide, 1, 0.8, 0.9, 2.5, 0.04, fill_color=ACCENT)

phases = [
    ("一", "基础环境搭建", "FastAPI + Vue3 + PostgreSQL + Redis"),
    ("二", "数据库与模型", "SQLAlchemy ORM 模型 + 仓储层"),
    ("三", "Agent 抽象层", "BaseAgent 基类 + 规则引擎兜底"),
    ("四", "前端 UI 框架", "Vue3 组件 + TailwindCSS + 五大模块"),
    ("五", "星火大模型集成", "HTTP 客户端 + 双通道策略"),
    ("六", "LangGraph 工作流", "多 Agent 协同 + 评估回流"),
    ("七", "讯飞语音接入", "ASR + TTS + 语音服务封装"),
    ("八", "RAG 知识库", "文档解析 + 向量检索 + 问答"),
    ("九", "学习评估闭环", "评估指标 + 报告生成 + 画像更新"),
    ("十", "Docker 部署", "Compose 编排 + Nginx + 一键启动"),
    ("十一", "用户认证", "JWT + bcrypt + Vue Router + 权限管理"),
]

for i, (num, title, desc) in enumerate(phases):
    col = i % 2
    row = i // 2
    x = 0.8 + col * 6.2
    y = 1.2 + row * 0.95

    _add_shape(slide, 1, x, y, 0.55, 0.55, fill_color=ACCENT if col == 0 else PRIMARY)
    _add_textbox(slide, x, y + 0.05, 0.55, 0.45, num, font_size=18, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    _add_textbox(slide, x + 0.7, y + 0.0, 5.0, 0.3, title, font_size=15, color=BLACK, bold=True)
    _add_textbox(slide, x + 0.7, y + 0.35, 5.0, 0.25, desc, font_size=11, color=GRAY)

_slide_number(slide, 24)


# ===========================================================================
# Slide 25: 部署与运维
# ===========================================================================
_section_header(slide := prs.slides.add_slide(prs.slide_layouts[6]), 12, "部署与运维", "Docker 容器化与一键部署")
_slide_number(slide, 25)

slide = prs.slides.add_slide(prs.slide_layouts[6])
_add_bg(slide, WHITE)
_add_textbox(slide, 0.8, 0.4, 5, 0.5, "部署与运维", font_size=28, color=PRIMARY, bold=True)
_add_shape(slide, 1, 0.8, 0.9, 2.5, 0.04, fill_color=ACCENT)

_card(slide, 0.8, 1.3, 5.8, 3.0, "Docker 容器化", [
    "docker/Dockerfile.backend - 后端镜像",
    "docker/Dockerfile.frontend - 前端镜像",
    "docker/docker-compose.yml - 服务编排",
    "docker/nginx-frontend.conf - Nginx 配置",
    "PostgreSQL + Redis + ChromaDB 容器化",
    "支持 Windows 与 Linux 双平台",
], title_color=PRIMARY)

_card(slide, 7.0, 1.3, 5.8, 3.0, "一键启动", [
    "PowerShell 启动脚本 (Windows)",
    "Bash 启动脚本 (Linux/macOS)",
    "自动构建镜像与启动容器",
    "健康检查确保服务可用",
    "环境变量通过 .env 配置",
    "首次启动自动创建管理员",
], title_color=ACCENT)

_card(slide, 0.8, 4.8, 5.8, 2.2, "本地开发", [
    "后端：uvicorn backend.main:app --reload",
    "前端：npm run dev (Vite HMR)",
    "Vite 代理 /api → http://localhost:8000",
    "支持热重载，开发体验友好",
], title_color=PRIMARY)

_card(slide, 7.0, 4.8, 5.8, 2.2, "运维要点", [
    "日志配置：结构化日志输出",
    "Redis 缓存：会话与临时数据",
    "健康检查端点：GET /api/health",
    "语音状态查询：GET /api/voice/status",
], title_color=ACCENT)

_slide_number(slide, 26)


# ===========================================================================
# Slide 27: 总结与展望
# ===========================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])
_add_bg(slide, DARK_BG)

_add_shape(slide, 1, 1.5, 2.0, 0.8, 0.06, fill_color=ACCENT)
_add_textbox(slide, 1.5, 0.8, 10, 0.8, "总结与展望", font_size=40, color=WHITE, bold=True)
_add_textbox(slide, 1.5, 1.8, 10, 0.5, "项目亮点与未来规划", font_size=20, color=ACCENT)

# 亮点
highlights = [
    ("多智能体协同", "10+ Agent 通过 LangGraph 编排，实现从画像到评估的全链路智能化"),
    ("双通道容错", "大模型 + 规则引擎双通道，保障系统在不可用环境下稳定运行"),
    ("RAG 知识增强", "文档解析 + 向量检索 + 大模型生成，提供精准知识服务"),
    ("语音交互", "讯飞 ASR/TTS 集成，支持语音输入输出，提升学习体验"),
    ("评估闭环", "学习评估 → 画像更新 → 路径调整，形成持续优化闭环"),
    ("权限管理", "JWT 认证 + 角色权限，保障系统安全与数据隔离"),
    ("工程化", "Docker 一键部署 + 前后端分离 + 类型安全，开发效率高"),
]

for i, (title, desc) in enumerate(highlights):
    y = 2.6 + i * 0.6
    _add_textbox(slide, 1.5, y, 2.0, 0.4, f"  {title}", font_size=16, color=ACCENT, bold=True)
    _add_textbox(slide, 3.8, y, 8.5, 0.4, desc, font_size=14, color=RGBColor(0xD1, 0xD5, 0xDB))

# 未来规划
_add_shape(slide, 1, 1.5, 6.8, 0.8, 0.03, fill_color=PRIMARY)
_add_textbox(slide, 1.5, 6.9, 10, 0.4, "未来规划", font_size=18, color=WHITE, bold=True)

future = [
    "多模态学习：接入图像理解与生成能力",
    "学习分析：数据驱动的学习行为深度分析",
    "协作学习：支持小组学习与同伴互评",
    "移动端适配：PWA 或小程序版本",
]
for i, item in enumerate(future):
    _add_textbox(slide, 1.8 + (i % 2) * 5.5, 7.4 + (i // 2) * 0.4, 5.0, 0.35, f"  {item}", font_size=13, color=RGBColor(0x9C, 0xA3, 0xAF))

_slide_number(slide, 27)


# ===========================================================================
# Slide 28: 感谢页
# ===========================================================================
slide = prs.slides.add_slide(prs.slide_layouts[6])
_add_bg(slide, DARK_BG)

_add_shape(slide, 1, 5.0, 3.5, 3.3, 0.06, fill_color=ACCENT)
_add_textbox(slide, 1.5, 2.5, 10, 1.0, "感谢聆听", font_size=52, color=WHITE, bold=True)
_add_textbox(slide, 5.0, 3.8, 3.3, 0.5, "EduAgent", font_size=24, color=ACCENT)
_add_textbox(slide, 5.0, 4.4, 3.3, 0.4, "AI 驱动的个性化学习智能体平台", font_size=14, color=RGBColor(0x93, 0xA3, 0xBA))

_add_textbox(slide, 1.5, 5.5, 10, 0.4, "FastAPI + Vue3 + LangGraph  |  PostgreSQL + Redis + ChromaDB  |  Docker + Nginx", font_size=12, color=GRAY)

# ---------------------------------------------------------------------------
# 保存
# ---------------------------------------------------------------------------
output_path = Path(__file__).resolve().parent.parent / "EduAgent_项目讲解.pptx"
prs.save(str(output_path))
logger.info("PPT 已生成: %s (共 %d 页)", output_path, len(prs.slides))
print(f"PPT 已生成: {output_path}")
print(f"共 {len(prs.slides)} 页幻灯片")