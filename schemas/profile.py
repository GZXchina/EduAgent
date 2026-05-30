from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StudentProfile(BaseModel):
    """架构文档定义的结构化画像字段。"""

    knowledge_level: str = Field(default="unknown", description="beginner/intermediate/advanced")
    learning_style: str = Field(default="unknown", description="visual/auditory/reading/kinesthetic")
    weakness: str = Field(default="", description="薄弱知识点")
    goal: str = Field(default="unknown", description="学习目标标识")
    study_time: str = Field(default="unknown", description="如 1h/day")

    major: str = Field(default="", description="专业")
    learning_goal_text: str = Field(default="", description="学习目标原文")
    learning_base: str = Field(default="", description="学习基础描述")
    learning_style_text: str = Field(default="", description="学习风格原文")
    raw_input: str = Field(default="", description="用户原始输入")

    @classmethod
    def from_llm_dict(cls, data: dict[str, Any], raw_input: str = "") -> "StudentProfile":
        return cls(
            knowledge_level=str(data.get("knowledge_level", "unknown")),
            learning_style=str(data.get("learning_style", "unknown")),
            weakness=str(data.get("weakness", "")),
            goal=str(data.get("goal", "unknown")),
            study_time=str(data.get("study_time", "unknown")),
            major=str(data.get("major", "")),
            learning_goal_text=str(data.get("learning_goal_text", data.get("goal_text", ""))),
            learning_base=str(data.get("learning_base", data.get("knowledge_base", ""))),
            learning_style_text=str(data.get("learning_style_text", "")),
            raw_input=raw_input or str(data.get("raw_input", "")),
        )


class ProfileBuildRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = Field(default=None, min_length=1, max_length=64)


class LearningStep(BaseModel):
    """学习路径中的一个阶段/步骤。"""

    week: int = Field(description="周数")
    title: str = Field(description="阶段名称")
    duration: str = Field(description="时长描述")
    topics: list[str] = Field(description="知识点列表")
    resources: list[str] = Field(description="推荐资源类型")
    assessment: str = Field(description="评估方式")


class LearningPath(BaseModel):
    """个性化学习路径模型。"""

    path_name: str = Field(description="学习路径名称")
    total_weeks: int = Field(description="预计完成周数")
    steps: list[LearningStep] = Field(description="学习步骤列表")
    focus_areas: list[str] = Field(description="重点关注领域")
    suggestions: list[str] = Field(description="学习建议")
    source: str = Field(default="heuristic", description="spark | heuristic")

    def to_markdown(self) -> str:
        """转换为Markdown格式的学习路径说明。"""
        lines = [f"## 学习路径：{self.path_name}", ""]
        lines.append(f"**预计周期**: {self.total_weeks} 周")
        lines.append(f"**重点关注**: {', '.join(self.focus_areas)}")
        lines.append("")
        lines.append("### 学习进度安排")
        lines.append("")

        for step in self.steps:
            lines.append(f"#### 第 {step.week} 周：{step.title}")
            lines.append(f"- **时长**: {step.duration}")
            lines.append(f"- **学习内容**: {', '.join(step.topics)}")
            lines.append(f"- **推荐资源**: {', '.join(step.resources)}")
            lines.append(f"- **评估方式**: {step.assessment}")
            lines.append("")

        if self.suggestions:
            lines.append("### 学习建议")
            lines.append("")
            for i, suggestion in enumerate(self.suggestions, 1):
                lines.append(f"{i}. {suggestion}")

        return "\n".join(lines)


class ProfileResponse(BaseModel):
    session_id: str
    profile: StudentProfile
    source: str = Field(description="spark | heuristic")
    cached: bool = False


class LearningPathResponse(BaseModel):
    session_id: str
    profile: StudentProfile
    learning_path: LearningPath


class QuizQuestion(BaseModel):
    """一道练习题。"""

    question_type: str = Field(description="题型: choice/blank/true_false/programming")
    difficulty: str = Field(description="难度: easy/medium/hard")
    question: str = Field(description="题目内容")
    options: list[str] | None = Field(default=None, description="选择题选项")
    answer: str = Field(description="正确答案")
    explanation: str = Field(description="答案解析")
    knowledge_point: str = Field(description="关联知识点")


class QuizSet(BaseModel):
    """一组练习题。"""

    topic: str = Field(description="练习主题")
    total_count: int = Field(description="题目总数")
    questions: list[QuizQuestion] = Field(description="题目列表")
    suggestions: list[str] = Field(description="学习建议")
    source: str = Field(default="heuristic", description="spark | heuristic")

    def to_markdown(self) -> str:
        """转换为Markdown格式的练习题。"""
        lines = [f"## {self.topic} 练习题集", ""]
        lines.append(f"**题目数量**: {self.total_count} 道")
        lines.append("")

        for i, q in enumerate(self.questions, 1):
            lines.append(f"### {'='*20}")
            lines.append(f"**题目 {i}** [{q.question_type}] [{q.difficulty}]")
            lines.append(f"**知识点**: {q.knowledge_point}")
            lines.append("")
            lines.append(q.question)

            if q.options:
                for opt in q.options:
                    lines.append(f"- {opt}")
            lines.append("")
            lines.append(f"**答案**: {q.answer}")
            lines.append(f"**解析**: {q.explanation}")
            lines.append("")

        if self.suggestions:
            lines.append("### 学习建议")
            for s in self.suggestions:
                lines.append(f"- {s}")

        return "\n".join(lines)


class CodeExample(BaseModel):
    """一个代码案例。"""

    title: str = Field(description="案例标题")
    description: str = Field(description="案例说明")
    code: str = Field(description="代码内容")
    language: str = Field(description="编程语言")
    output: str | None = Field(default=None, description="预期输出")
    key_points: list[str] = Field(description="关键知识点")
    difficulty: str = Field(default="medium", description="难度: easy/medium/hard")


class CodeSet(BaseModel):
    """一组代码案例。"""

    topic: str = Field(description="主题")
    total_count: int = Field(description="案例总数")
    examples: list[CodeExample] = Field(description="代码案例列表")
    suggestions: list[str] = Field(description="学习建议")
    source: str = Field(default="heuristic", description="spark | heuristic")

    def to_markdown(self) -> str:
        """转换为Markdown格式的代码案例。"""
        lines = [f"## {self.topic} 代码案例集", ""]
        lines.append(f"**案例数量**: {self.total_count} 个")
        lines.append("")

        for i, ex in enumerate(self.examples, 1):
            lines.append(f"### {'='*20}")
            lines.append(f"**案例 {i}: {ex.title}** [{ex.difficulty}]")
            lines.append("")
            lines.append(f"**说明**: {ex.description}")
            lines.append("")
            lines.append("```" + ex.language)
            lines.append(ex.code)
            lines.append("```")

            if ex.output:
                lines.append("")
                lines.append(f"**预期输出**:")
                lines.append("```")
                lines.append(ex.output)
                lines.append("```")

            lines.append("")
            lines.append(f"**关键知识点**: {', '.join(ex.key_points)}")
            lines.append("")

        if self.suggestions:
            lines.append("### 学习建议")
            for s in self.suggestions:
                lines.append(f"- {s}")

        return "\n".join(lines)


class PPTSlide(BaseModel):
    """PPT中的一页幻灯片。"""

    slide_number: int = Field(description="幻灯片编号")
    title: str = Field(description="页面标题")
    content: list[str] = Field(description="页面内容要点")
    notes: str | None = Field(default=None, description="演讲备注")


class PPTDeck(BaseModel):
    """一组PPT课件。"""

    topic: str = Field(description="课件主题")
    total_slides: int = Field(description="幻灯片总数")
    slides: list[PPTSlide] = Field(description="幻灯片列表")
    source: str = Field(default="heuristic", description="spark | heuristic")

    def to_markdown(self) -> str:
        """转换为Markdown格式的课件。"""
        lines = [f"# {self.topic} 课件", ""]
        lines.append(f"**幻灯片数量**: {self.total_slides} 页\n")

        for slide in self.slides:
            lines.append(f"## 第 {slide.slide_number} 页：{slide.title}")
            lines.append("")
            for point in slide.content:
                lines.append(f"- {point}")
            lines.append("")
            if slide.notes:
                lines.append(f"> **备注**: {slide.notes}")
                lines.append("")

        return "\n".join(lines)


class MindMapNode(BaseModel):
    """思维导图中的一个节点。"""

    id: str = Field(description="节点ID")
    text: str = Field(description="节点文本")
    children: list["MindMapNode"] = Field(default_factory=list, description="子节点")


class MindMap(BaseModel):
    """思维导图。"""

    topic: str = Field(description="主题")
    root: MindMapNode = Field(description="根节点")
    source: str = Field(default="heuristic", description="spark | heuristic")

    def to_mermaid(self) -> str:
        """转换为Mermaid思维导图格式。"""
        lines = ["mindmap"]
        lines.append(self._node_to_mermaid(self.root, 0))
        return "\n".join(lines)

    def _node_to_mermaid(self, node: MindMapNode, depth: int) -> str:
        indent = "  " * depth
        result = [f"{indent}  {node.text}"]
        for child in node.children:
            result.append(self._node_to_mermaid(child, depth + 1))
        return "\n".join(result)

    def to_markdown(self) -> str:
        """转换为Markdown格式的思维导图（带层级）。"""
        lines = [f"## {self.topic} 思维导图", ""]
        lines.append(self._node_to_markdown(self.root, 0))
        return "\n".join(lines)

    def _node_to_markdown(self, node: MindMapNode, depth: int) -> str:
        indent = "  " * depth
        bullet = "-" if depth > 0 else "-"
        result = [f"{indent}{bullet} {node.text}"]
        for child in node.children:
            result.append(self._node_to_markdown(child, depth + 1))
        return "\n".join(result)


class VideoScriptScene(BaseModel):
    """视频脚本中的一个场景。"""

    scene_number: int = Field(description="场景编号")
    duration: str = Field(description="时长")
    content: str = Field(description="场景内容")
    visual_description: str = Field(description="视觉效果描述")
    audio_notes: str | None = Field(default=None, description="音频备注")


class VideoScript(BaseModel):
    """视频脚本。"""

    topic: str = Field(description="视频主题")
    total_duration: str = Field(description="总时长")
    scenes: list[VideoScriptScene] = Field(description="场景列表")
    suggestions: list[str] = Field(description="拍摄建议")
    source: str = Field(default="heuristic", description="spark | heuristic")

    def to_markdown(self) -> str:
        """转换为Markdown格式的视频脚本。"""
        lines = [f"## {self.topic} 视频脚本", ""]
        lines.append(f"**总时长**: {self.total_duration}")
        lines.append("")

        for scene in self.scenes:
            lines.append(f"### 场景 {scene.scene_number}（{scene.duration}）")
            lines.append(f"**内容**: {scene.content}")
            lines.append(f"**视觉效果**: {scene.visual_description}")
            if scene.audio_notes:
                lines.append(f"**音频**: {scene.audio_notes}")
            lines.append("")

        if self.suggestions:
            lines.append("### 拍摄建议")
            for s in self.suggestions:
                lines.append(f"- {s}")

        return "\n".join(lines)