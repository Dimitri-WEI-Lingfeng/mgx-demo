# 为 Message 类添加 Tool Calling 支持字段

**日期**: 2026-02-02  
**类型**: 功能增强

## 概述

为 `Message` schema 添加 `tool_call_id` 和 `tool_calls` 字段，以更好地支持 LangChain 的工具调用功能，使消息结构与 LangChain 的 AIMessage 和 ToolMessage 完全兼容。

## 修改内容

### 1. 修改 `Message` 类

**文件**: `src/shared/schemas/message.py`

添加了两个新字段：

#### `tool_call_id` (str | None)
- **用途**: 用于 ToolMessage 角色
- **说明**: 标识该工具结果消息是响应哪个工具调用的
- **默认值**: None

#### `tool_calls` (list[dict[str, Any]])
- **用途**: 用于 AIMessage 角色（assistant）
- **说明**: 包含 AI 调用的工具列表
- **格式**: 每个元素包含 `id`、`name`、`args` 字段
- **默认值**: 空列表

**代码变更**:
```python
class Message(BaseModel):
    # ... 其他字段
    
    # Tool calling support (langchain compatible)
    tool_call_id: str | None = Field(
        None,
        description="Tool call ID (for ToolMessage role)"
    )
    tool_calls: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Tool calls made by assistant (for AIMessage role)"
    )
```

### 2. 更新示例文档

添加了三个完整的示例，展示不同使用场景：

1. **简单的 Assistant 消息**: 不包含工具调用
2. **带工具调用的 AI 消息**: 包含 `tool_calls` 列表
3. **工具结果消息**: 包含 `tool_call_id`

### 3. 更新 `MessageDAO.create_message_from_langchain`

**文件**: `src/mgx_api/dao/message_dao.py`

增强了从 LangChain 消息转换的逻辑：

#### 处理 AIMessage 的 tool_calls
```python
# Extract tool_calls (for AIMessage)
tool_calls: list[dict[str, Any]] = []
if isinstance(langchain_msg, AIMessage) and hasattr(langchain_msg, "tool_calls"):
    for tool_call in langchain_msg.tool_calls or []:
        tool_calls.append({
            "id": tool_call.get("id"),
            "name": tool_call.get("name"),
            "args": tool_call.get("args"),
        })
```

#### 处理 ToolMessage 的 tool_call_id
```python
# Extract tool_call_id (for ToolMessage)
tool_call_id = None
if isinstance(langchain_msg, ToolMessage):
    tool_call_id = getattr(langchain_msg, "tool_call_id", None)
```

## 使用场景示例

### 场景 1: Assistant 调用工具

```python
from shared.schemas import Message

# AI 决定调用工具
ai_message = Message(
    message_id="msg_001",
    session_id="sess_123",
    role="assistant",
    content="Let me check the weather for you.",
    tool_calls=[
        {
            "id": "call_abc123",
            "name": "get_weather",
            "args": {"city": "San Francisco", "unit": "celsius"}
        }
    ],
    timestamp=time.time(),
)
```

### 场景 2: 工具返回结果

```python
# 工具执行后返回结果
tool_message = Message(
    message_id="msg_002",
    session_id="sess_123",
    parent_id="msg_001",  # 引用 AI 消息
    role="tool",
    content="Temperature: 18°C, Conditions: Sunny",
    tool_call_id="call_abc123",  # 关联到工具调用
    timestamp=time.time(),
)
```

### 场景 3: 从 LangChain 消息转换

```python
from langchain_core.messages import AIMessage
from mgx_api.dao import MessageDAO

# LangChain AIMessage with tool calls
lc_message = AIMessage(
    content="Let me search that for you.",
    tool_calls=[
        {
            "id": "call_xyz",
            "name": "web_search",
            "args": {"query": "Python async tutorial"}
        }
    ]
)

# 自动转换并保存
dao = MessageDAO()
message_id = await dao.create_message_from_langchain(
    session_id="sess_123",
    langchain_msg=lc_message,
    agent_name="assistant",
)
```

## 向后兼容性

✅ **完全向后兼容**:

1. 两个新字段都有默认值
   - `tool_call_id`: None
   - `tool_calls`: 空列表

2. 现有代码无需修改即可正常工作

3. 工具调用信息同时存储在：
   - 顶层字段（`tool_call_id`, `tool_calls`）- 新格式
   - `content_parts` 列表 - 旧格式（向后兼容）

## 数据结构对照

### LangChain vs 本系统

| LangChain | 本系统 Message | 说明 |
|-----------|---------------|------|
| `AIMessage.tool_calls` | `tool_calls` | AI 调用的工具列表 |
| `ToolMessage.tool_call_id` | `tool_call_id` | 工具调用 ID |
| `AIMessage.content` | `content` | 文本内容 |
| `BaseMessage.id` | `message_id` | 消息唯一标识 |

## 数据库影响

- ✅ 无需数据库迁移
- ✅ 现有消息自动获得默认值
- ✅ MongoDB 的灵活 schema 自动支持新字段

## 测试建议

1. 测试创建带 tool_calls 的消息
2. 测试创建带 tool_call_id 的消息
3. 测试从 LangChain 消息转换
4. 测试与现有代码的兼容性

## 后续优化建议

1. 添加工具调用的 schema 验证
2. 添加工具调用追踪和统计
3. 考虑添加工具调用的性能监控
4. 为工具调用添加重试机制
