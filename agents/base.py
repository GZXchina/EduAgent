from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    name: str = "base"

    @abstractmethod
    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """接收共享状态，返回需要合并回状态的片段。"""
