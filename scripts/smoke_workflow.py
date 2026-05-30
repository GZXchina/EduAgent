import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from workflows.graph import build_workflow, default_initial_state


async def main() -> None:
    g = build_workflow()
    r = await g.ainvoke(default_initial_state("hello"))
    print("messages:", len(r.get("messages", [])))


if __name__ == "__main__":
    asyncio.run(main())
