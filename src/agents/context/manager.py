"""上下文管理器 - 管理当前的 AgentContext 实例。

这个模块提供全局的上下文管理，替代之前的全局变量方式。
使用 contextvars 来支持异步场景，并提供线程传播机制。
"""

import contextvars
import threading
from typing import Optional, Callable, Any

from .base import AgentContext


# 使用 contextvars 作为主要存储机制
_context_var: contextvars.ContextVar[Optional[AgentContext]] = contextvars.ContextVar('agent_context', default=None)

# 全局备用存储（用于跨线程访问）
_global_context: Optional[AgentContext] = None
_global_context_lock = threading.Lock()


def set_context(context: AgentContext, *, global_fallback: bool = True) -> None:
    """设置当前上下文。
    
    Args:
        context: AgentContext 实例
        global_fallback: 是否同时设置全局备用上下文，用于跨线程访问（默认 True）
    """
    _context_var.set(context)
    
    if global_fallback:
        global _global_context
        with _global_context_lock:
            _global_context = context


def get_context() -> Optional[AgentContext]:
    """获取当前上下文。
    
    优先从 contextvars 获取，如果没有则尝试从全局备用获取。
    
    Returns:
        AgentContext 实例，如果未设置则返回 None
    """
    # 优先使用 contextvars（支持异步）
    ctx = _context_var.get()
    if ctx is not None:
        return ctx
    
    # 回退到全局上下文（支持跨线程）
    with _global_context_lock:
        return _global_context


def require_context() -> AgentContext:
    """获取当前上下文，如果未设置则抛出异常。
    
    Returns:
        AgentContext 实例
    
    Raises:
        RuntimeError: 如果上下文未设置
    """
    context = get_context()
    if context is None:
        raise RuntimeError(
            "AgentContext not set. "
            "Please call set_context() with an AgentContext instance first."
        )
    return context


def clear_context(*, clear_global: bool = True) -> None:
    """清除当前上下文。
    
    Args:
        clear_global: 是否同时清除全局备用上下文（默认 True）
    """
    _context_var.set(None)
    
    if clear_global:
        global _global_context
        with _global_context_lock:
            _global_context = None


def run_in_context(context: AgentContext, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """在指定上下文中运行函数（支持跨线程）。
    
    这对于需要在新线程中运行代码但需要访问上下文的场景很有用。
    
    Args:
        context: 要使用的上下文
        func: 要运行的函数
        *args: 函数参数
        **kwargs: 函数关键字参数
    
    Returns:
        函数的返回值
    
    Example:
        def worker():
            ctx = get_context()
            return ctx.workspace_id
        
        # 在新线程中运行，但使用指定的上下文
        thread = threading.Thread(
            target=run_in_context,
            args=(context, worker)
        )
        thread.start()
        thread.join()
    """
    # 在新的 context 中运行
    ctx = contextvars.copy_context()
    
    def wrapper():
        _context_var.set(context)
        return func(*args, **kwargs)
    
    return ctx.run(wrapper)


class ContextScope:
    """上下文作用域管理器 - 支持 with 语句。
    
    示例：
        with ContextScope(context):
            # 在这个作用域内使用 context
            workspace_path = get_context().get_workspace_path()
    """
    
    def __init__(self, context: AgentContext):
        self.context = context
        self.token = None
    
    def __enter__(self):
        # 使用 contextvars 的 token 机制来保证正确恢复
        self.token = _context_var.set(self.context)
        return self.context
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 使用 token 恢复之前的值
        _context_var.reset(self.token)
        return False
