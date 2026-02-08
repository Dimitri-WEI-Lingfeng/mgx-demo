# Schema 修改：添加 agent_name 字段

**日期**: 2026-02-01  
**类型**: Schema 增强

## 概述

为 `Event` 和 `Message` schema 添加了 `agent_name` 字段，用于标识创建该事件或消息的 agent。同时修改了 `EventStore` 和 `MessageStore` 的接口，使其接受完整的对象实例而非单独的参数。

## 修改详情

### 1. Schema 修改

#### Event Schema (`src/shared/schemas/event.py`)
- ✅ 添加 `agent_name: str | None` 字段
- 字段描述：创建该事件的 agent 名称

#### Message Schema (`src/shared/schemas/message.py`)
- ✅ 添加 `agent_name: str | None` 字段
- 字段描述：创建该消息的 agent 名称

### 2. 接口修改

#### EventStore 接口 (`src/agents/context/base.py`)
**修改前：**
```python
async def create_event(
    self,
    event_type: str,
    data: dict,
    message_id: str | None = None,
    trace_id: str | None = None,
) -> Any:
```

**修改后：**
```python
async def create_event(self, event: Event) -> Any:
```

#### MessageStore 接口 (`src/agents/context/base.py`)
**修改前：**
```python
async def create_message(
    self,
    role: str,
    content: str,
    trace_id: str | None = None,
) -> Any:
```

**修改后：**
```python
async def create_message(self, message: Message) -> Any:
```

### 3. 实现修改

#### DatabaseEventStore (`src/agents/context/database.py`)
- ✅ 更新 `create_event` 方法接受 `Event` 实例
- ✅ 直接传递给 DAO 层

#### DatabaseMessageStore (`src/agents/context/database.py`)
- ✅ 更新 `create_message` 方法接受 `Message` 实例
- ✅ 直接传递给 DAO 层

#### InMemoryEventStore (`src/agents/context/memory.py`)
- ✅ 更新 `create_event` 方法接受 `Event` 实例
- ✅ 使用 `model_dump()` 转换为 dict 存储

#### InMemoryMessageStore (`src/agents/context/memory.py`)
- ✅ 更新 `create_message` 方法接受 `Message` 实例
- ✅ 使用 `model_dump()` 转换为 dict 存储

### 4. DAO 层修改

#### EventDAO (`src/mgx_api/dao/event_dao.py`)
**修改前：**
```python
async def create_event(
    self,
    session_id: str,
    event_type: EventType,
    data: dict[str, Any],
    ...
) -> Event:
```

**修改后：**
```python
async def create_event(self, event: Event) -> Event:
```

#### MessageDAO (`src/mgx_api/dao/message_dao.py`)
**修改前：**
```python
async def create_message(
    self,
    session_id: str,
    role: str,
    content: str,
    ...
) -> Message:
```

**修改后：**
```python
async def create_message(self, message: Message) -> Message:
```

- ✅ 同时更新 `create_message_from_langchain` 方法，添加 `agent_name` 参数

### 5. 调用代码修改

#### run_agent.py (`src/agents/run_agent.py`)
- ✅ 添加辅助函数 `create_event()` 和 `create_message()` 用于简化实例创建
- ✅ 更新所有调用点，为 `code_generation_agent` 和 `team_agent` 设置 agent_name

#### quick_start_memory_mode.py (`src/agents/quick_start_memory_mode.py`)
- ✅ 更新示例代码使用新的 API

#### test_context.py (`scripts/test_context.py`)
- ✅ 更新测试代码使用新的 API

## 迁移指南

### 对于现有代码

如果你的代码调用了 `create_event` 或 `create_message`，需要进行以下修改：

**修改前：**
```python
await context.event_store.create_event(
    event_type=EventType.AGENT_START.value,
    data={"prompt": prompt},
    trace_id=trace_id,
)
```

**修改后：**
```python
import time
import uuid
from shared.schemas import Event, EventType

event = Event(
    event_id=str(uuid.uuid4()),
    session_id=context.session_id,
    timestamp=time.time(),
    event_type=EventType.AGENT_START,
    data={"prompt": prompt},
    trace_id=trace_id,
    agent_name="your_agent_name",
)
await context.event_store.create_event(event)
```

### 使用辅助函数（推荐）

为了简化代码，可以使用辅助函数（参考 `run_agent.py`）：

```python
def create_event(
    session_id: str,
    event_type: EventType,
    data: dict,
    message_id: str | None = None,
    trace_id: str | None = None,
    agent_name: str | None = None,
) -> Event:
    """创建 Event 实例的辅助函数。"""
    return Event(
        event_id=str(uuid.uuid4()),
        session_id=session_id,
        timestamp=time.time(),
        event_type=event_type,
        agent_name=agent_name,
        data=data,
        message_id=message_id,
        trace_id=trace_id,
    )
```

## 优势

1. **更强的类型安全**：使用 Pydantic 模型确保字段类型正确
2. **更好的可追溯性**：通过 `agent_name` 字段可以追踪每个事件和消息的来源
3. **更清晰的接口**：方法签名更简单，只需要一个参数
4. **更易于扩展**：未来添加新字段只需修改 schema，不需要修改所有调用点
5. **更好的验证**：Pydantic 自动进行字段验证

## 测试

运行以下命令验证修改：

```bash
# 运行快速开始示例
uv run python src/agents/quick_start_memory_mode.py

# 运行上下文测试
uv run python scripts/test_context.py
```

## 注意事项

1. **向后兼容性**：这是一个破坏性变更，所有调用 `create_event` 和 `create_message` 的代码都需要更新
2. **数据库迁移**：现有数据库记录不包含 `agent_name` 字段（该字段为可选）
3. **agent_name 是可选的**：如果不需要追踪 agent，可以设置为 `None`

## 相关文件

- `src/shared/schemas/event.py`
- `src/shared/schemas/message.py`
- `src/agents/context/base.py`
- `src/agents/context/database.py`
- `src/agents/context/memory.py`
- `src/mgx_api/dao/event_dao.py`
- `src/mgx_api/dao/message_dao.py`
- `src/agents/run_agent.py`
- `src/agents/quick_start_memory_mode.py`
- `scripts/test_context.py`
