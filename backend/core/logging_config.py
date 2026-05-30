from __future__ import annotations

import logging
import sys

from backend.settings import get_settings


def setup_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.terminator = "\n"
    
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    handler.setFormatter(formatter)
    
    logging.basicConfig(
        level=level,
        handlers=[handler],
    )
