"""直接测试工作流，不通过HTTP。"""

import asyncio
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from workflows.simple_graph import build_simple_workflow, default_initial_state


async def main() -> None:
    print("直接测试简化工作流...")
    
    graph = build_simple_workflow()
    state = default_initial_state("你好，我想学习Python", "test_001")
    
    print("开始执行工作流...")
    try:
        result = await graph.ainvoke(state)
        print(f"工作流执行完成!")
        print(f"结果包含的keys: {list(result.keys())}")
        messages = result.get("messages", [])
        print(f"消息数量: {len(messages)}")
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = str(msg.get("content", ""))[:100]
            print(f"  [{i}] {role}: {content}...")
    except Exception as e:
        print(f"工作流执行失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
