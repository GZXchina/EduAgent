from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.settings import get_settings


def split_text(text: str, *, source: str = "") -> list[dict]:
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""],
    )
    chunks = splitter.split_text(text)
    return [
        {"text": c.strip(), "metadata": {"source": source, "chunk_index": i}}
        for i, c in enumerate(chunks)
        if c.strip()
    ]
