"""将 knowledge/ 目录课程资料入库到 ChromaDB。"""

import os
import sys
from pathlib import Path

# 设置 HuggingFace 国内镜像源，解决网络访问问题
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

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
