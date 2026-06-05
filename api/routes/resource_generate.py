"""简化的资源生成 API - 直接调用模型，不走工作流"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.integrations.spark.client import get_spark_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/resource", tags=["resource"])


class ResourceGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="学习主题")
    resource_type: Literal["ppt", "quiz", "code", "mindmap", "video"] = Field(
        ..., description="资源类型"
    )
    model: str | None = Field(default=None, description="AI 模型 ID")


class ResourceGenerateResponse(BaseModel):
    content: str = Field(description="生成的内容（Markdown 格式）")
    resource_type: str
    model_used: str


# 精准 Prompt 模板 - 确保只生成对应类型的内容
RESOURCE_PROMPTS: dict[str, str] = {
    "ppt": """你是一位专业的课件设计师。请根据主题生成一份简洁的 PPT 课件大纲。

要求：
- 只输出 PPT 大纲，不要输出其他任何内容
- 使用 Markdown 格式
- 包含：标题页 + 3-5 个章节
- 每个章节包含 2-3 个要点
- 不要输出学习建议、练习题或其他任何额外内容

主题：{topic}
""",
    "quiz": """你是一位出题专家。请根据主题生成 5 道选择题。

要求：
- 只输出题目，不要输出任何解释、知识点总结或其他内容
- 使用以下格式：

**题目 1**
题目内容
- A. 选项 A
- B. 选项 B
- C. 选项 C
- D. 选项 D

答案：X

**题目 2**
...

主题：{topic}
""",
    "code": """你是一位编程讲师。请根据主题生成 3 个代码示例。

要求：
- 只输出代码和简要注释，不要输出其他解释文字
- 使用 Markdown 代码块格式
- 每个代码示例包含：
  - 代码块（带语言标识）
  - 一行简短注释说明代码作用
- 不要输出理论讲解、运行结果或其他内容

主题：{topic}
""",
    "mindmap": """你是一位思维导图专家。请根据主题生成 Mermaid 格式的思维导图。

要求：
- 只输出 Mermaid 代码，用 ```mermaid 包裹
- 使用 mindmap 语法
- 根节点为主题名称
- 包含 3-4 个主要分支
- 每个分支 2-3 个子节点
- 不要输出任何文字说明或其他内容

主题：{topic}
""",
    "video": """你是一位视频脚本编剧。请根据主题生成一份简短的视频脚本。

要求：
- 只输出脚本，不要输出其他内容
- 时长控制在 3-5 分钟
- 使用以下格式：

| 时间 | 画面 | 旁白 |
|------|------|------|
| 0:00-0:30 | 开场画面 | 旁白内容 |
| ... | ... | ... |

主题：{topic}
""",
}


@router.post("/generate", response_model=ResourceGenerateResponse)
async def generate_resource(body: ResourceGenerateRequest) -> ResourceGenerateResponse:
    """简化版资源生成 - 直接调用模型，不走工作流"""
    spark = get_spark_client()
    
    if not spark.configured:
        raise RuntimeError("AI 模型未配置")
    
    # 获取对应资源类型的 Prompt
    prompt_template = RESOURCE_PROMPTS.get(body.resource_type)
    if not prompt_template:
        raise ValueError(f"不支持的资源类型: {body.resource_type}")
    
    # 填充主题
    user_prompt = prompt_template.format(topic=body.topic)
    
    messages = [
        {"role": "user", "content": user_prompt}
    ]
    
    # 调用模型
    content = await spark.chat(messages, model=body.model)
    
    # 确定实际使用的模型
    model_used = body.model or spark.settings.spark_model
    
    return ResourceGenerateResponse(
        content=content,
        resource_type=body.resource_type,
        model_used=model_used,
    )
