# Agent Context 抽象层

提供统一的上下文管理接口，支持数据库和内存两种模式，便于本地开发和生产部署。

## 核心概念

### AgentContext

抽象基类，定义了 agent 运行所需的上下文接口：

- `session_id`: 会话 ID
- `workspace_id`: 工作区 ID
- `event_store`: 事件存储接口
- `message_store`: 消息存储接口
- `get_workspace_path()`: 获取工作区路径
- `get_container_name()`: 获取容器名称

### EventStore 和 MessageStore

抽象接口，用于存储事件和消息：

- `EventStore.create_event()`: 创建事件
- `MessageStore.create_message()`: 创建消息

## 两种实现

### 1. InMemoryContext（内存模式）

用于本地开发和测试，不需要数据库连接。

**特点：**
- ✅ 无需数据库
- ✅ 快速启动
- ✅ 便于调试
- ✅ 支持事件和消息查询
- ✅ 自动生成 ID

**使用示例：**

```python
from agents.context import InMemoryContext, set_context

# 自动生成 ID
context = InMemoryContext()

# 或指定 ID 和路径
context = InMemoryContext(
    session_id="my-session",
    workspace_id="my-workspace",
    workspace_path="./workspaces/test"
)

# 设置为当前上下文
set_context(context)

# 查看事件和消息
events = context.get_events()
messages = context.get_messages()
```

### 2. DatabaseContext（数据库模式）

用于生产环境，使用数据库存储事件和消息。

**特点：**
- ✅ 持久化存储
- ✅ 支持多实例
- ✅ 完整的审计日志
- ✅ 与现有系统集成

**使用示例：**

```python
from agents.context import DatabaseContext, set_context

# 需要提供 session_id 和 workspace_id
context = DatabaseContext(
    session_id="session-123",
    workspace_id="workspace-456"
)

# 设置为当前上下文
set_context(context)
```

## 上下文管理器

### 基础使用

```python
from agents.context import set_context, get_context, require_context, clear_context

# 设置上下文
set_context(context)

# 获取上下文（可能返回 None）
ctx = get_context()

# 获取上下文（如果未设置则抛出异常）
ctx = require_context()

# 清除上下文
clear_context()
```

### 使用 ContextScope（推荐）

```python
from agents.context import InMemoryContext, ContextScope

context = InMemoryContext()

# 使用 with 语句自动管理上下文
with ContextScope(context):
    # 在这个作用域内使用 context
    from agents.context import get_context
    ctx = get_context()  # 返回 context
    
    # 调用需要上下文的函数
    run_some_agent()

# 离开作用域后自动清除
```

## 在 Agent 中使用

### 工具模块

工具模块会自动从上下文获取信息：

```python
from agents.web_app_team.tools.workspace_tools import read_file

# 不需要手动传递 workspace_id
content = read_file("README.md")  # 自动从 context 获取路径
```

### 创建 Agent

```python
from agents.context import InMemoryContext, set_context
from agents.agent_factory import create_team_agent

# 1. 创建并设置上下文
context = InMemoryContext()
set_context(context)

# 2. 创建 agent（不需要传递 workspace_id）
team = create_team_agent(framework="nextjs")
```

### 完整示例

```python
import asyncio
from agents.context import InMemoryContext, ContextScope
from agents.agent_factory import create_team_agent
from agents.web_app_team.state import create_initial_state

async def main():
    # 创建上下文
    context = InMemoryContext(
        workspace_path="./my-project"
    )
    
    # 使用 ContextScope 管理上下文
    with ContextScope(context):
        # 创建团队
        team = create_team_agent(framework="nextjs")
        
        # 创建初始状态
        state = create_initial_state(
            workspace_id=context.workspace_id,
            framework="nextjs",
            user_prompt="创建一个待办事项应用"
        )
        
        # 运行 agent
        result = await asyncio.to_thread(team.invoke, state)
        
        # 查看结果
        print(f"状态: {result.get('current_stage')}")
        print(f"事件数: {len(context.get_events())}")
        print(f"消息数: {len(context.get_messages())}")

asyncio.run(main())
```

## 本地开发脚本

项目提供了便捷的本地运行脚本：

```bash
# 使用脚本运行
uv run python scripts/run_agent_local.py \
  --prompt "创建一个博客应用" \
  --framework nextjs \
  --workspace ./test-workspace

# 查看帮助
uv run python scripts/run_agent_local.py --help
```

## 环境变量配置

### run_agent.py 支持的环境变量

#### 通用变量
- `RUN_MODE`: 运行模式（`database` 或 `memory`，默认 `database`）
- `AGENT_MODE`: Agent 模式（`team` 或 `single`，默认 `team`）
- `FRAMEWORK`: 目标框架（`nextjs` 或 `fastapi-vite`）
- `PROMPT`: 用户需求描述
- `TRACE_ID`: 追踪 ID（可选）

#### Database 模式特有
- `SESSION_ID`: 会话 ID（必需）
- `WORKSPACE_ID`: 工作区 ID（必需）

#### Memory 模式特有
- `SESSION_ID`: 会话 ID（可选，不提供则自动生成）
- `WORKSPACE_ID`: 工作区 ID（可选，不提供则自动生成）
- `WORKSPACE_PATH`: 工作区路径（可选，不提供则使用默认路径）

### 示例

```bash
# Database 模式
export RUN_MODE=database
export SESSION_ID=sess-123
export WORKSPACE_ID=ws-456
export FRAMEWORK=nextjs
export PROMPT="创建一个博客"
python src/agents/run_agent.py

# Memory 模式
export RUN_MODE=memory
export FRAMEWORK=nextjs
export PROMPT="创建一个博客"
export WORKSPACE_PATH=./my-workspace
python src/agents/run_agent.py
```

## 并发支持

上下文管理器使用 **混合存储策略**，结合 `contextvars` 和全局备用机制：

**重要特性：**
- ✅ **跨线程访问**：通过全局备用机制，子线程可以访问主线程设置的上下文
- ✅ **线程隔离**：每个线程可以有独立的上下文
- ✅ **异步兼容**：优先使用 contextvars，完美支持 asyncio
- ✅ **LangChain 兼容**：解决 agent 工具在不同线程执行时无法访问上下文的问题

### 工作原理

当你调用 `set_context(context)` 时，上下文会被存储在两个地方：

1. **contextvars**：用于同一线程和异步任务的上下文传播
2. **全局备用存储**：用于跨线程访问（带锁保护）

`get_context()` 会优先从 contextvars 获取，如果没有则从全局备用获取。

### 基本用法（推荐）

大多数情况下，只需在主线程设置一次上下文即可：

```python
from agents.context import InMemoryContext, set_context

# 在主线程设置上下文
context = InMemoryContext(workspace_id="my-workspace")
set_context(context)

# LangChain agent 和所有工具都能访问这个上下文
# 即使工具在不同线程中执行
```

### 跨线程传播示例

```python
import threading
from agents.context import InMemoryContext, set_context, get_context

# 在主线程设置上下文
context = InMemoryContext(workspace_id="main-workspace")
set_context(context)

def worker():
    # 子线程可以访问主线程设置的上下文（通过全局备用）
    ctx = get_context()
    print(f"Worker context: {ctx.workspace_id}")  # 输出: main-workspace

thread = threading.Thread(target=worker)
thread.start()
thread.join()
```

### 线程独立上下文示例

```python
import threading
from agents.context import InMemoryContext, set_context, get_context

def worker(worker_id):
    # 每个线程可以设置独立的上下文
    # 使用 global_fallback=False 避免覆盖全局备用
    context = InMemoryContext(workspace_id=f"workspace-{worker_id}")
    set_context(context, global_fallback=False)
    
    # 这个线程的上下文不会影响其他线程
    ctx = get_context()
    print(f"Worker {worker_id}: {ctx.workspace_id}")

# 启动多个线程
threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

### 高级用法：run_in_context

如果需要在新线程中显式地使用特定上下文：

```python
import threading
from agents.context import InMemoryContext, run_in_context, get_context

context = InMemoryContext(workspace_id="special-workspace")

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
```

## 测试

### 单元测试示例

```python
import pytest
from agents.context import InMemoryContext, set_context, clear_context

@pytest.fixture
def memory_context():
    """测试用的内存上下文。"""
    context = InMemoryContext()
    set_context(context)
    yield context
    clear_context()

def test_workspace_tools(memory_context):
    """测试工作区工具。"""
    from agents.web_app_team.tools.workspace_tools import write_file, read_file
    
    # 写入文件
    result = write_file("test.txt", "Hello, World!")
    assert "成功" in result
    
    # 读取文件
    content = read_file("test.txt")
    assert content == "Hello, World!"
    
    # 验证事件
    events = memory_context.get_events()
    assert len(events) >= 0
```

## 最佳实践

1. **使用 ContextScope**：推荐使用 `with ContextScope(context)` 自动管理上下文

2. **本地开发使用 Memory 模式**：快速迭代，无需数据库

3. **生产环境使用 Database 模式**：持久化存储，完整的审计日志

4. **单元测试使用 Memory 模式**：快速、独立、可重复

5. **清理上下文**：使用完毕后调用 `clear_context()` 或使用 `ContextScope`

6. **避免全局状态**：不要缓存上下文实例，总是通过 `get_context()` 获取

## 故障排查

### RuntimeError: AgentContext not set

**原因**：工具或 agent 尝试访问上下文，但上下文未设置。

**解决**：
```python
from agents.context import InMemoryContext, set_context

context = InMemoryContext()
set_context(context)  # 确保在使用前设置上下文
```

### 上下文获取为 None

**原因**：在不同线程中访问上下文。

**解决**：确保每个线程都设置了自己的上下文，或者使用 `require_context()` 抛出更明确的错误。

### 事件或消息未记录

**原因**：可能使用了错误的上下文类型或未正确创建事件。

**调试**：
```python
context = get_context()
print(f"Context type: {type(context)}")
print(f"Session ID: {context.session_id}")

# 在 Memory 模式下查看事件
if isinstance(context, InMemoryContext):
    events = context.get_events()
    print(f"Events: {len(events)}")
```

## API 参考

### InMemoryContext

```python
class InMemoryContext(AgentContext):
    def __init__(
        self,
        session_id: str | None = None,
        workspace_id: str | None = None,
        workspace_path: str | Path | None = None,
    ):
        """创建内存上下文。
        
        Args:
            session_id: 会话 ID（可选，默认自动生成）
            workspace_id: 工作区 ID（可选，默认自动生成）
            workspace_path: 工作区路径（可选，默认使用配置路径）
        """
    
    def get_events(self) -> list[dict]:
        """获取所有事件。"""
    
    def get_messages(self) -> list[dict]:
        """获取所有消息。"""
```

### DatabaseContext

```python
class DatabaseContext(AgentContext):
    def __init__(self, session_id: str, workspace_id: str):
        """创建数据库上下文。
        
        Args:
            session_id: 会话 ID（必需）
            workspace_id: 工作区 ID（必需）
        """
```

### 上下文管理函数

```python
def set_context(context: AgentContext) -> None:
    """设置当前线程的上下文。"""

def get_context() -> Optional[AgentContext]:
    """获取当前线程的上下文（可能返回 None）。"""

def require_context() -> AgentContext:
    """获取当前上下文，如果未设置则抛出 RuntimeError。"""

def clear_context() -> None:
    """清除当前线程的上下文。"""
```

### ContextScope

```python
class ContextScope:
    """上下文作用域管理器。
    
    使用示例：
        with ContextScope(context):
            # 在此作用域内使用 context
            pass
    """
    def __init__(self, context: AgentContext):
        """初始化作用域。"""
```

## 相关资源

- [变更日志](../../../change-logs/2025-02-01-context-abstraction.md)
- [Web App Team 文档](../../web_app_team/README.md)
- [本地运行脚本](../../../scripts/run_agent_local.py)
