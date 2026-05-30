"""将 knowledge/ 目录课程资料入库到 ChromaDB。"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from backend.core.logging_config import setup_logging
from rag.ingest import get_ingest_summary, ingest_knowledge_directory


def main() -> None:
    setup_logging()
    n = ingest_knowledge_directory()
    summary = get_ingest_summary()
    print(f"入库完成，新增/更新切片约 {n} 条")
    print(summary)


if __name__ == "__main__":
    main()
