from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agents.base import BaseAgent

logger = logging.getLogger(__name__)

BLOCKED_CONTENT_KEYWORDS = ["暴力", "赌博", "色情", "政治", "黑客", "病毒", "木马", "攻击"]
SUSPICIOUS_PATTERNS = ["import os", "subprocess", "eval(", "exec(", "os.system", "__import__"]


def _prompt_path() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts" / "safety_agent.md"


def load_safety_prompt() -> str:
    path = _prompt_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "你是内容安全审核助手，检查生成的学习资源是否包含不当内容。"


def check_content_safety(content: str | list[str]) -> tuple[bool, str]:
    """检查内容安全性，返回(is_safe, reason)。"""
    if not content:
        return True, ""

    if isinstance(content, list):
        combined_text = "\n".join(str(c) for c in content)
        content_lower = combined_text.lower()
    else:
        content_lower = str(content).lower()

    for keyword in BLOCKED_CONTENT_KEYWORDS:
        if keyword in content_lower:
            return False, f"包含敏感关键词: {keyword}"

    return True, ""


def check_code_safety(code: str) -> tuple[bool, str]:
    """检查代码安全性。"""
    if not code:
        return True, ""

    for pattern in SUSPICIOUS_PATTERNS:
        if pattern in code:
            if pattern in ["import os", "subprocess", "eval(", "exec("]:
                if "os.system" not in code and "__import__" not in code:
                    continue
            return False, f"包含可疑代码模式: {pattern}"

    return True, ""


def review_resource(resource: dict[str, Any], resource_type: str) -> dict[str, Any]:
    """审核单个资源的安全性。"""
    issues: list[str] = []
    is_safe = True

    if resource_type == "ppt":
        for slide in resource.get("slides", []):
            content = slide.get("content", "")
            safe, reason = check_content_safety(content)
            if not safe:
                issues.append(f"PPT第{slide.get('slide_number', '?')}页: {reason}")
                is_safe = False

    elif resource_type == "quiz":
        for q in resource.get("questions", []):
            content = q.get("question", "") + q.get("answer", "")
            safe, reason = check_content_safety(content)
            if not safe:
                issues.append(f"题目{q.get('id', '?')}: {reason}")
                is_safe = False

    elif resource_type == "code":
        for ex in resource.get("examples", []):
            code = ex.get("code", "")
            safe, reason = check_code_safety(code)
            if not safe:
                issues.append(f"代码案例{ex.get('title', '?')}: {reason}")
                is_safe = False

    elif resource_type == "mindmap":
        content = resource.get("root", {}).get("text", "")
        safe, reason = check_content_safety(content)
        if not safe:
            issues.append(f"思维导图根节点: {reason}")
            is_safe = False

    elif resource_type == "video":
        for scene in resource.get("scenes", []):
            content = scene.get("content", "")
            safe, reason = check_content_safety(content)
            if not safe:
                issues.append(f"视频第{scene.get('scene_number', '?')}幕: {reason}")
                is_safe = False

    return {
        "type": resource_type,
        "is_safe": is_safe,
        "issues": issues,
        "reviewed": True
    }


class SafetyAgent(BaseAgent):
    """安全审核Agent：审核生成的学习资源内容安全性。"""

    name = "safety"

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        resource_result = state.get("resource_result", {})
        ppt_deck = state.get("ppt_deck", {})
        quiz_set = state.get("quiz_set", {})
        code_set = state.get("code_set", {})
        mindmap = state.get("mindmap", {})
        video_script = state.get("video_script", {})

        reviews: list[dict[str, Any]] = []

        if ppt_deck:
            reviews.append(review_resource(ppt_deck, "ppt"))
        if quiz_set:
            reviews.append(review_resource(quiz_set, "quiz"))
        if code_set:
            reviews.append(review_resource(code_set, "code"))
        if mindmap:
            reviews.append(review_resource(mindmap, "mindmap"))
        if video_script:
            reviews.append(review_resource(video_script, "video"))

        all_safe = all(r["is_safe"] for r in reviews)

        merged = {
            "reviewed": True,
            "all_safe": all_safe,
            "reviews": reviews,
            "reviewed_by": self.name,
        }

        if all_safe:
            message = f"【安全审核】通过，共审核{len(reviews)}项资源，未发现问题内容。"
        else:
            unsafe_count = sum(1 for r in reviews if not r["is_safe"])
            message = f"【安全审核】发现问题！{len(reviews)}项中有{unsafe_count}项需要处理。\n"
            for r in reviews:
                if not r["is_safe"]:
                    message += f"- {r['type']}: {', '.join(r['issues'])}\n"

        return {
            "resource_result": merged,
            "messages": [{"role": "assistant", "content": message}],
        }