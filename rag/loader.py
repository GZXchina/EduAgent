from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".pdf", ".docx", ".doc"}


def load_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix in {".docx", ".doc"}:
        return _load_docx(path)
    raise ValueError(f"不支持的文件类型: {path}")


def _load_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _load_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def iter_knowledge_files(knowledge_dir: str | Path) -> list[Path]:
    root = Path(knowledge_dir)
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return []
    files: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES and p.name != ".gitkeep":
            files.append(p)
    return sorted(files)
