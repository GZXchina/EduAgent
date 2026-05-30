"""简化测试工作流，排除资源生成阶段。"""

import asyncio
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from workflows.graph import default_initial_state
from agents.profile_agent import ProfileAgent
from agents.planner_agent import PlannerAgent


async def main() -> None:
    print("测试简化工作流...")
    
    state = default_initial_state("你好", "test_session_001")
    print(f"初始状态: {state}")
    
    # 测试ProfileAgent
    profile_agent = ProfileAgent()
    print("\n--- 测试 ProfileAgent ---")
    try:
        profile_result = await profile_agent.run(dict(state))
        print(f"Profile结果: {profile_result}")
        state.update(profile_result)
    except Exception as e:
        print(f"ProfileAgent失败: {e}")
        return
    
    # 测试PlannerAgent
    planner_agent = PlannerAgent()
    print("\n--- 测试 PlannerAgent ---")
    try:
        planner_result = await planner_agent.run(dict(state))
        print(f"Planner结果: {planner_result}")
        state.update(planner_result)
    except Exception as e:
        print(f"PlannerAgent失败: {e}")
        return
    
    print("\n测试完成！")


if __name__ == "__main__":
    asyncio.run(main())
