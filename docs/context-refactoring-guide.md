# Context 重构指南

## 概述

本次重构将 `web_app_team` 中依赖 `session_id` 和 `workspace_id` 的部分抽象成统一的上下文层，支持两种运行模式：

- **Memory 模式**：用于本地开发，无需数据库
- **Database 模式**：用于生产环境，使用数据库存储

## 快速开始

### 本地开发（推荐）

```bash
# 使用便捷脚本
uv run python scripts/run_agent_local.py \
  --prompt "创建一个待办事项应用" \
  --framework nextjs
```

### 编程方式

```python
import asyncio
from agents.context import InMemoryContext, set_context
from agents.agent_factory import create_team_agent
from agents.web_app_team.state import create_initial_state

async def main():
    # 1. 创建内存上下文
    context = InMemoryContext()
    set_context(context)
    
    # 2. 创建团队
    team = create_team_agent(framework="nextjs")
    
    # 3. 运行
    state = create_initial_state(
        workspace_id=context.workspace_id,
        framework="nextjs",
        user_prompt="创建一个博客应用"
    )
    result = await asyncio.to_thread(team.invoke, state)
    
    # 4. 查看结果
    print(f"完成阶段: {result.get('current_stage')}")
    print(f"事件数: {len(context.get_events())}")

asyncio.run(main())
```

## 核心变更

### 1. 新增模块

```
src/agents/context/
├── __init__.py       # 导出接口
├── base.py           # 抽象基类
├── memory.py         # 内存实现
├── database.py       # 数据库实现
├── manager.py        # 上下文管理
└── README.md         # 详细文档
```

### 2. 工具模块变更

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

### 3. Agent 创建变更

**之前：**
```python
agent = create_boss_agent(llm, workspace_id="workspace-123")
```

**之后：**
```python
context = InMemoryContext(workspace_id="workspace-123")
set_context(context)
agent = create_boss_agent(llm)
```

## 运行模式对比

| 特性 | Memory 模式 | Database 模式 |
|------|-------------|---------------|
| 数据库 | ❌ 不需要 | ✅ 需要 |
| 持久化 | ❌ 不持久化 | ✅ 持久化 |
| 启动速度 | 🚀 快速 | 🐢 较慢 |
| 调试 | ✅ 便于调试 | ⚠️ 需查询数据库 |
| 适用场景 | 本地开发、测试 | 生产部署 |
| 事件查询 | ✅ `context.get_events()` | ❌ 需要 DAO |
| ID 生成 | 🔄 自动生成 | 📝 需要提供 |

## 环境变量配置

### Memory 模式

```bash
export RUN_MODE=memory
export FRAMEWORK=nextjs
export PROMPT="创建应用"
export WORKSPACE_PATH=./my-workspace  # 可选

python src/agents/run_agent.py
```

### Database 模式

```bash
export RUN_MODE=database
export SESSION_ID=session-123
export WORKSPACE_ID=workspace-456
export FRAMEWORK=nextjs
export PROMPT="创建应用"

python src/agents/run_agent.py
```

## 测试

```bash
# 运行上下文测试
uv run python scripts/test_context.py

# 测试本地运行
uv run python scripts/run_agent_local.py \
  --prompt "创建一个简单的计数器应用" \
  --framework nextjs
```

## 常见问题

### Q1: RuntimeError: AgentContext not set

**原因**：工具或 agent 尝试访问上下文，但上下文未设置。

**解决**：
```python
from agents.context import InMemoryContext, set_context
context = InMemoryContext()
set_context(context)  # 确保在使用前设置
```

### Q2: 如何在单元测试中使用？

**答案**：使用 pytest fixture：
```python
import pytest
from agents.context import InMemoryContext, set_context, clear_context

@pytest.fixture
def agent_context():
    context = InMemoryContext()
    set_context(context)
    yield context
    clear_context()

def test_something(agent_context):
    # 使用 agent_context
    pass
```

### Q3: 如何切换回数据库模式？

**答案**：使用 `DatabaseContext` 替代 `InMemoryContext`：
```python
from agents.context import DatabaseContext, set_context
context = DatabaseContext(
    session_id="session-123",
    workspace_id="workspace-456"
)
set_context(context)
```

## 优势

✅ **解耦依赖**：工具不再依赖全局变量  
✅ **便于测试**：无需数据库即可测试  
✅ **快速开发**：本地运行更加便捷  
✅ **灵活扩展**：可轻松添加新的实现  
✅ **并发安全**：使用线程本地存储  

## 相关文档

- [上下文 API 详细文档](../src/agents/context/README.md)
- [变更日志](../change-logs/2025-02-01-context-abstraction.md)
- [本地运行脚本](../scripts/run_agent_local.py)
- [测试脚本](../scripts/test_context.py)

## 下一步

1. ✅ 基础重构完成
2. 🔄 编写单元测试（使用 InMemoryContext）
3. 🔄 集成测试验证
4. 📝 更新 API 文档
5. 🚀 部署到生产环境

## 反馈与贡献

如果遇到问题或有改进建议，请：
1. 查看 [Context README](../src/agents/context/README.md)
2. 运行测试脚本检查问题
3. 提交 issue 或 PR
