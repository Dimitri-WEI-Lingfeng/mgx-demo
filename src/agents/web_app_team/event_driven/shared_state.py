"""共享的制品状态，线程安全的异步读写。

所有 Agent 通过 SharedArtifactState 共享文档制品（requirements、PRD、design 等），
避免通过消息链传递大量文档内容。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SharedArtifactState:
    """Agent 共享的制品状态。

    通过 asyncio.Lock 保证并发安全。
    """

    workspace_id: str = ""
    framework: str = "nextjs"

    requirements_doc: str | None = None
    prd_doc: str | None = None
    design_doc: str | None = None
    tasks_doc: str | None = None
    code_summary: str | None = None
    test_report: str | None = None

    _extra: dict[str, Any] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def update(self, **kwargs: Any) -> None:
        """线程安全更新字段。"""
        async with self._lock:
            for k, v in kwargs.items():
                if hasattr(self, k) and not k.startswith("_"):
                    setattr(self, k, v)
                else:
                    self._extra[k] = v

    async def get(self, key: str, default: Any = None) -> Any:
        """线程安全读取。"""
        async with self._lock:
            if hasattr(self, key) and not key.startswith("_"):
                return getattr(self, key)
            return self._extra.get(key, default)

    async def snapshot(self) -> dict[str, Any]:
        """返回当前状态快照。"""
        async with self._lock:
            return {
                "workspace_id": self.workspace_id,
                "framework": self.framework,
                "requirements_doc": self.requirements_doc,
                "prd_doc": self.prd_doc,
                "design_doc": self.design_doc,
                "tasks_doc": self.tasks_doc,
                "code_summary": self.code_summary,
                "test_report": self.test_report,
                **self._extra,
            }
