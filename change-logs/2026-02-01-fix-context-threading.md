# 修复：上下文在多线程环境下的访问问题

**日期**: 2026-02-01  
**类型**: Bug Fix  
**影响范围**: `src/agents/context/manager.py`

## 问题描述

在使用 LangChain agent 时，如果 agent 在不同线程中执行工具调用，工具函数无法访问通过 `set_context()` 设置的上下文，导致 `RuntimeError: AgentContext not set` 错误。

### 原因分析

之前的实现使用 `threading.local()` 来存储上下文：

```python
_thread_local = threading.local()

def set_context(context):
    _thread_local.context = context

def get_context():
    return getattr(_thread_local, "context", None)
```

**问题**：`threading.local()` 的数据是线程隔离的，子线程无法访问父线程设置的数据。

当 LangChain agent 在新线程中执行工具时，工具函数调用 `require_context()` 会失败，因为新线程中没有上下文。

## 解决方案

采用**混合存储策略**，结合 `contextvars` 和全局备用机制：

```python
import contextvars
import threading

# contextvars 用于异步和同线程传播
_context_var: contextvars.ContextVar[Optional[AgentContext]] = contextvars.ContextVar('agent_context', default=None)

# 全局备用存储用于跨线程访问
_global_context: Optional[AgentContext] = None
_global_context_lock = threading.Lock()

def set_context(context: AgentContext, *, global_fallback: bool = True):
    """同时设置 contextvars 和全局备用"""
    _context_var.set(context)
    
    if global_fallback:
        global _global_context
        with _global_context_lock:
            _global_context = context

def get_context():
    """优先从 contextvars 获取，没有则从全局备用获取"""
    ctx = _context_var.get()
    if ctx is not None:
        return ctx
    
    with _global_context_lock:
        return _global_context
```

### 优势

1. **跨线程访问**：通过全局备用机制，子线程可以访问主线程设置的上下文
2. **异步兼容**：contextvars 完美支持 asyncio
3. **向后兼容**：API 保持不变，不需要修改现有代码
4. **线程安全**：全局备用使用锁保护
5. **灵活性**：可以选择是否设置全局备用（`global_fallback` 参数）

## 修改的文件

- `src/agents/context/manager.py`: 核心修改
- `src/agents/context/__init__.py`: 导出新的 `run_in_context` 函数
- `src/agents/context/README.md`: 更新文档

## 新增功能

### `run_in_context()` 函数

用于在特定上下文中运行函数（高级用法）：

```python
from agents.context import run_in_context

def worker():
    ctx = get_context()
    return ctx.workspace_id

thread = threading.Thread(
    target=run_in_context,
    args=(context, worker)
)
thread.start()
thread.join()
```

## 测试

创建了全面的测试套件 (`test_context_fix.py`)，验证：

- ✅ 基本上下文设置和获取
- ✅ 子线程继承父线程上下文
- ✅ 多线程共享上下文
- ✅ 线程独立上下文

所有测试通过。

## 迁移指南

**无需任何修改**，现有代码可以直接使用：

```python
# 之前的代码（仍然有效）
context = InMemoryContext(workspace_path='./workspace')
set_context(context)

# agent 和工具现在可以在任何线程中访问上下文
agent = create_boss_agent(llm)
result = agent.invoke({"messages": [...]})
```

## 使用建议

对于大多数场景，推荐的使用方式：

1. 在主线程设置一次上下文：
   ```python
   set_context(context)
   ```

2. 让 agent 和工具自动访问：
   ```python
   ctx = require_context()  # 在任何线程都有效
   ```

如果需要每个线程独立的上下文，使用 `global_fallback=False`：

```python
set_context(context, global_fallback=False)
```

## 性能影响

- 最小的性能开销（一个锁操作）
- contextvars 访问非常快（O(1)）
- 全局备用仅在 contextvars 未设置时才访问
