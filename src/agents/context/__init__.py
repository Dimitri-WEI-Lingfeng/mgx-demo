"""Agent 上下文抽象层 - 支持数据库和内存两种模式。"""

from .base import AgentContext, EventStore, MessageStore
from .memory import InMemoryContext
from .database import DatabaseContext
from .manager import (
    set_context,
    get_context,
    require_context,
    clear_context,
    run_in_context,
    ContextScope,
)

__all__ = [
    # 基类和接口
    "AgentContext",
    "EventStore",
    "MessageStore",
    # 实现类
    "InMemoryContext",
    "DatabaseContext",
    # 上下文管理
    "set_context",
    "get_context",
    "require_context",
    "clear_context",
    "run_in_context",
    "ContextScope",
]
