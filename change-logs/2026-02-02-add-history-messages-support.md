# 添加历史消息支持

**日期**: 2026-02-02  
**类型**: 功能增强

## 概述

为 team agent 的初始状态添加历史消息支持，允许 agent 在继续对话时访问完整的会话历史。

## 修改内容

### 1. 修改 `create_initial_state` 函数

**文件**: `src/agents/web_app_team/state.py`

- 添加可选参数 `history_messages: list[BaseMessage] | None = None`
- 如果提供了历史消息，将其添加到初始状态的消息列表中
- 保持向后兼容性：如果不提供历史消息，行为与之前一致

**变更**:
```python
def create_initial_state(
    workspace_id: str,
    framework: str,
    user_prompt: str,
    history_messages: list[BaseMessage] | None = None,  # 新增参数
) -> TeamState:
    # 构建消息列表：历史消息 + 当前用户消息
    messages = []
    if history_messages:
        messages.extend(history_messages)
    messages.append(HumanMessage(content=user_prompt))
    
    return {
        "messages": messages,
        # ... 其他字段
    }
```

### 2. 修改 `run_team_agent_with_streaming` 函数

**文件**: `src/agents/run_agent.py`

- 在 `last_message_id` 不为 None 时，从数据库加载会话的历史消息
- 将历史消息转换为 LangChain 消息格式
- 传递给 `create_initial_state` 函数

**关键逻辑**:
```python
# 加载历史消息（如果需要）
history_messages = []
if last_message_id is not None:
    # 从数据库加载历史消息
    if isinstance(context.message_store, DatabaseMessageStore):
        messages = await context.message_store.dao.get_session_messages(
            session_id=session_id,
            limit=100  # 限制历史消息数量
        )
        
        # 转换为 LangChain 消息格式
        for msg in messages:
            if msg.role == "user":
                history_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                history_messages.append(AIMessage(content=msg.content))
            # ... 其他角色
```

### 3. 修改 `main` 函数

**文件**: `src/agents/run_agent.py`

- 从环境变量读取 `LAST_MESSAGE_ID`
- 传递给 `run_team_agent_with_streaming` 和 `run_agent_with_streaming`

## 使用方法

### 通过环境变量

```bash
# 设置 LAST_MESSAGE_ID 环境变量
export LAST_MESSAGE_ID="msg_123abc"
export SESSION_ID="sess_456def"
export WORKSPACE_ID="workspace_789"
export FRAMEWORK="nextjs"
export PROMPT="继续实现登录功能"
export AGENT_MODE="team"

# 运行 agent
uv run src/agents/run_agent.py
```

### 直接调用函数

```python
from agents.context import DatabaseContext
from agents.run_agent import run_team_agent_with_streaming

context = DatabaseContext(
    session_id="sess_456def",
    workspace_id="workspace_789",
)

result = await run_team_agent_with_streaming(
    context=context,
    framework="nextjs",
    prompt="继续实现登录功能",
    last_message_id="msg_123abc",  # 提供上一条消息 ID
)
```

## 行为说明

1. **首次对话** (last_message_id = None):
   - 不加载历史消息
   - 只包含当前用户的提示词
   - 行为与之前完全一致

2. **继续对话** (last_message_id != None):
   - 从数据库加载会话的所有历史消息（最多 100 条）
   - 按时间戳排序
   - 添加到初始状态的消息列表中
   - Agent 可以看到完整的对话上下文

## 向后兼容性

- ✅ `create_initial_state` 的 `history_messages` 参数是可选的
- ✅ 现有代码（`quick_start_memory_mode.py`, `run_agent_local.py`）无需修改即可正常工作
- ✅ 不提供 `last_message_id` 时，行为与之前完全一致

## 限制

1. **消息数量限制**: 当前限制为最多加载 100 条历史消息
2. **仅支持数据库模式**: 内存模式暂不支持历史消息加载
3. **仅支持 team agent**: 单 agent 模式（`run_agent_with_streaming`）暂不支持历史消息

## 后续优化建议

1. 添加消息数量限制的配置选项
2. 为内存模式添加历史消息支持
3. 考虑添加消息过滤（例如只加载特定类型的消息）
4. 添加消息摘要功能以减少 token 消耗
