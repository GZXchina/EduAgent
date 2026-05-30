from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from backend.settings import get_settings
from rag.chunker import split_text
from rag.loader import iter_knowledge_files, load_document
from rag.vector_store import add_chunks, collection_stats

logger = logging.getLogger(__name__)


def _file_id(path: Path, knowledge_root: Path) -> str:
    rel = path.relative_to(knowledge_root).as_posix()
    digest = hashlib.md5(rel.encode()).hexdigest()[:8]
    return f"{digest}:{rel}"


def ingest_file(path: Path, knowledge_root: Path) -> int:
    text = load_document(path)
    rel = path.relative_to(knowledge_root).as_posix()
    chunks = split_text(text, source=rel)
    fid = _file_id(path, knowledge_root)
    n = add_chunks(chunks, file_id=fid)
    logger.info("入库 %s -> %s 切片", rel, n)
    return n


def ingest_knowledge_directory(knowledge_dir: str | None = None) -> int:
    settings = get_settings()
    root = Path(knowledge_dir or settings.knowledge_dir)
    root.mkdir(parents=True, exist_ok=True)
    total = 0
    for path in iter_knowledge_files(root):
        try:
            total += ingest_file(path, root)
        except Exception as exc:
            logger.exception("入库失败 %s: %s", path, exc)
    return total


def get_ingest_summary() -> dict:
    stats = collection_stats()
    files = [p.name for p in iter_knowledge_files(get_settings().knowledge_dir)]
    return {"vector_count": stats["count"], "collection": stats["name"], "knowledge_files": files}
