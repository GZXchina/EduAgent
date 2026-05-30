"""阶段四学习规划Agent测试（不依赖星火 API）。"""

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from agents.planner_agent import PlannerAgent, heuristic_path
from schemas.profile import StudentProfile


def test_heuristic_path() -> None:
    """测试规则引擎生成学习路径。"""
    profile = StudentProfile(
        knowledge_level="beginner",
        learning_style="visual",
        weakness="循环",  # 使用中文
        goal="lanqiao_competition",
        study_time="1h/day",
        major="计算机科学"
    )
    
    path = heuristic_path(profile)
    
    print(f"Testing heuristic path...")
    print(f"  path_name: {path.path_name}")
    print(f"  total_weeks: {path.total_weeks}")
    print(f"  focus_areas: {path.focus_areas}")
    print(f"  suggestions: {path.suggestions}")
    
    assert path.path_name == "蓝桥杯Python竞赛之路"
    assert path.total_weeks == 8  # beginner + 1h/day -> 8周
    assert "循环" in path.focus_areas
    assert path.steps
    assert len(path.steps) == path.total_weeks
    
    print(f"heuristic path ok: {path.path_name}")


async def test_planner_agent() -> None:
    """测试PlannerAgent（使用规则引擎兜底）。"""
    agent = PlannerAgent()
    
    # 测试有画像的情况
    state_with_profile = {
        "student_profile": {
            "knowledge_level": "beginner",
            "learning_style": "visual",
            "weakness": "函数",
            "goal": "lanqiao_competition",
            "study_time": "2h/day",
            "major": "软件工程"
        },
        "session_id": "test-session-planner"
    }
    
    result = await agent.run(state_with_profile)
    
    print(f"\nPlanner Agent result:")
    print(f"  learning_path: {result.get('learning_path', {})}")
    
    assert "learning_path" in result
    assert "messages" in result
    
    path_name = result["learning_path"]["path_name"]
    print(f"  actual path_name: '{path_name}'")
    
    # 检查是否包含"蓝桥杯"或"Python学习"
    assert "蓝桥杯" in path_name or "Python" in path_name, f"Unexpected path_name: {path_name}"
    
    total_weeks = result["learning_path"]["total_weeks"]
    print(f"  total_weeks: {total_weeks}")
    
    # 2h/day 应该缩短周期
    assert total_weeks <= 8, f"Expected <= 8 weeks for 2h/day, got {total_weeks}"
    
    print(f"planner agent with profile ok")
    
    # 测试无画像的情况
    state_empty = {"user_input": "test", "session_id": "test-empty"}
    result_empty = await agent.run(state_empty)
    assert "learning_path" in result_empty
    print(f"planner agent without profile ok")


def test_markdown_output() -> None:
    """测试学习路径的Markdown输出。"""
    profile = StudentProfile(
        knowledge_level="intermediate",
        goal="job_preparation",
        study_time="1h/day"
    )
    
    path = heuristic_path(profile)
    md = path.to_markdown()
    
    assert "#" in md  # 包含标题
    assert "周" in md  # 包含周数
    assert "- **时长**:" in md  # 包含时长
    assert "- **学习内容**:" in md  # 包含学习内容
    
    print("markdown output ok")


def main() -> None:
    test_heuristic_path()
    asyncio.run(test_planner_agent())
    test_markdown_output()
    print("\n=== Phase 4 Planner Agent Tests Passed ===")


if __name__ == "__main__":
    main()