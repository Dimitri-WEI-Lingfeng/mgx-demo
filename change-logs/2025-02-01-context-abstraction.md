# 上下文抽象重构 - 支持内存模式

**日期**: 2025-02-01
**类型**: 重构
**影响范围**: `src/agents/`

## 概述

重构了 web_app_team 中依赖 session_id 和 workspace_id 的部分，抽象出统一的上下文层（AgentContext），支持两种运行模式：

1. **Database 模式**（生产环境）：使用数据库存储事件和消息
2. **Memory 模式**（本地开发）：使用内存存储，无需数据库连接

## 核心变更

### 1. 新增上下文抽象层 (`src/agents/context/`)

创建了统一的上下文接口，包含：

- `AgentContext`: 抽象基类，定义统一接口
- `InMemoryContext`: 内存实现，用于本地开发
- `DatabaseContext`: 数据库实现，用于生产环境
- 上下文管理器：`set_context()`, `get_context()`, `require_context()`

**目录结构：**
```
src/agents/context/
├── __init__.py       # 导出接口
├── base.py           # 抽象基类
├── memory.py         # 内存实现
├── database.py       # 数据库实现
└── manager.py        # 上下文管理器
```

### 2. 重构工具模块

#### `workspace_tools.py`
- **之前**: 使用全局变量 `_workspace_id`
- **之后**: 从 `require_context()` 获取上下文
- 移除了 `set_workspace_id()` 函数

#### `docker_tools.py`
- **之前**: 使用全局变量 `_workspace_id`
- **之后**: 从 `require_context()` 获取上下文
- 移除了 `set_workspace_id()` 函数

### 3. 重构 Agent 创建函数

所有 agent 创建函数移除了 `workspace_id` 参数：

- `create_boss_agent(llm, callbacks)` ~~workspace_id~~
- `create_pm_agent(llm, callbacks)` ~~workspace_id~~
- `create_architect_agent(llm, framework, callbacks)` ~~workspace_id~~
- `create_pjm_agent(llm, callbacks)` ~~workspace_id~~
- `create_engineer_agent(llm, framework, callbacks)` ~~workspace_id~~
- `create_qa_agent(llm, callbacks)` ~~workspace_id~~

**使用方式：**
```python
# 之前
agent = create_boss_agent(llm, workspace_id="xxx")

# 之后
context = InMemoryContext(workspace_id="xxx")
set_context(context)
agent = create_boss_agent(llm)
```

### 4. 重构团队工厂函数

#### `create_web_app_team(framework, callbacks)`
- 移除 `workspace_id` 参数
- 通过 `get_context()` 获取上下文信息

#### `create_team_agent(framework, callbacks)`
- 移除 `workspace_id` 参数
- 需要先设置上下文

### 5. 重构运行脚本 (`run_agent.py`)

支持两种运行模式，通过环境变量 `RUN_MODE` 控制：

#### Database 模式（默认）
```bash
export RUN_MODE=database
export SESSION_ID=xxx
export WORKSPACE_ID=xxx
export FRAMEWORK=nextjs
export PROMPT="创建一个博客应用"
python src/agents/run_agent.py
```

#### Memory 模式（本地开发）
```bash
export RUN_MODE=memory
export WORKSPACE_PATH=/path/to/workspace  # 可选
export FRAMEWORK=nextjs
export PROMPT="创建一个博客应用"
python src/agents/run_agent.py
```

### 6. 新增本地运行脚本

创建了 `scripts/run_agent_local.py`，提供更友好的本地开发体验：

```bash
# 使用方式
uv run python scripts/run_agent_local.py \
  --prompt "创建一个任务管理应用" \
  --framework nextjs \
  --workspace ./my-workspace
```

## 使用示例

### 本地开发模式

```python
import asyncio
from agents.context import InMemoryContext, set_context
from agents.agent_factory import create_team_agent
from agents.web_app_team.state import create_initial_state

async def run_local():
    # 1. 创建内存上下文
    context = InMemoryContext(
        workspace_path="./my-workspace"
    )
    
    # 2. 设置上下文
    set_context(context)
    
    # 3. 创建团队
    team = create_team_agent(framework="nextjs")
    
    # 4. 创建初始状态
    state = create_initial_state(
        workspace_id=context.workspace_id,
        framework="nextjs",
        user_prompt="创建一个博客应用"
    )
    
    # 5. 运行
    result = await asyncio.to_thread(team.invoke, state)
    
    # 6. 查看事件和消息
    print(f"事件数: {len(context.get_events())}")
    print(f"消息数: {len(context.get_messages())}")

asyncio.run(run_local())
```

### 生产环境模式

```python
from agents.context import DatabaseContext, set_context
from agents.agent_factory import create_team_agent

# 1. 创建数据库上下文
context = DatabaseContext(
    session_id="session-123",
    workspace_id="workspace-456"
)

# 2. 设置上下文
set_context(context)

# 3. 创建并使用团队
team = create_team_agent(framework="nextjs")
# ... 运行 agent
```

## 优势

### 1. 解耦依赖
- 工具模块不再依赖全局变量
- Agent 创建不需要传递 workspace_id
- 更清晰的依赖关系

### 2. 便于测试
- 可以轻松创建测试上下文
- 不需要数据库连接即可测试
- 支持并发测试（线程本地存储）

### 3. 本地开发友好
- Memory 模式无需数据库
- 快速迭代和调试
- 事件和消息可查看

### 4. 灵活扩展
- 可以轻松添加新的上下文实现
- 统一的接口便于切换

## 迁移指南

### 如果你的代码直接使用 workspace_tools

**之前：**
```python
from agents.web_app_team.tools.workspace_tools import set_workspace_id

set_workspace_id("workspace-123")
```

**之后：**
```python
from agents.context import InMemoryContext, set_context

context = InMemoryContext(workspace_id="workspace-123")
set_context(context)
```

### 如果你创建 agent

**之前：**
```python
agent = create_boss_agent(llm, workspace_id="workspace-123")
```

**之后：**
```python
# 先设置上下文
context = InMemoryContext(workspace_id="workspace-123")
set_context(context)

# 再创建 agent
agent = create_boss_agent(llm)
```

### 如果你创建团队

**之前：**
```python
team = create_web_app_team(
    workspace_id="workspace-123",
    framework="nextjs"
)
```

**之后：**
```python
# 先设置上下文
context = InMemoryContext(workspace_id="workspace-123")
set_context(context)

# 再创建团队
team = create_web_app_team(framework="nextjs")
```

## 兼容性

- ✅ 完全向后兼容数据库模式
- ✅ 支持所有现有功能
- ✅ 不影响生产环境部署
- ✅ 新增内存模式不影响现有代码

## 测试

建议测试以下场景：

1. **本地开发**：使用 `scripts/run_agent_local.py` 测试
2. **单元测试**：使用 `InMemoryContext` 编写测试
3. **集成测试**：使用 `DatabaseContext` 测试完整流程
4. **并发测试**：验证线程本地存储的正确性

## 后续计划

1. 为所有 agent 添加单元测试（使用 InMemoryContext）
2. 添加更多上下文实现（如 Redis、File-based）
3. 改进事件和消息的结构化日志
4. 添加性能监控和指标收集

## 相关文件

- `src/agents/context/` - 上下文抽象层
- `src/agents/web_app_team/tools/workspace_tools.py` - 工作区工具
- `src/agents/web_app_team/tools/docker_tools.py` - Docker 工具
- `src/agents/web_app_team/team.py` - 团队工厂
- `src/agents/agent_factory.py` - Agent 工厂
- `src/agents/run_agent.py` - 运行脚本
- `scripts/run_agent_local.py` - 本地运行脚本
