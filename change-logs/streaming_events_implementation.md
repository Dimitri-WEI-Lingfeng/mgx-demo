# Stream 事件和消息存储实现

## 修改日期
2026-02-02

## 修改内容

### 1. 定义事件数据类型 (`src/shared/schemas/event.py`)

为不同的事件类型定义了类型化的数据结构：

- **生命周期事件**
  - `AgentStartData`: AGENT_START 事件数据
  - `AgentEndData`: AGENT_END 事件数据
  - `AgentErrorData`: AGENT_ERROR 事件数据

- **LLM 事件**
  - `LLMStartData`: LLM_START 事件数据
  - `LLMStreamData`: LLM_STREAM 事件数据（增量）
  - `LLMEndData`: LLM_END 事件数据

- **工具事件**
  - `ToolStartData`: TOOL_START 事件数据
  - `ToolEndData`: TOOL_END 事件数据

- **消息事件**
  - `MessageDeltaData`: MESSAGE_DELTA 事件数据（增量）
  - `MessageCompleteData`: MESSAGE_COMPLETE 事件数据

- **团队工作流事件**（新增）
  - `NodeStartData`: NODE_START 事件数据（节点开始执行）
  - `NodeEndData`: NODE_END 事件数据（节点执行完成）
  - `StageChangeData`: STAGE_CHANGE 事件数据（工作流阶段变更）

- **完成事件**
  - `FinishData`: FINISH 事件数据

### 2. 新增事件类型

在 `EventType` 枚举中新增：
```python
NODE_START = "node_start"      # 节点开始执行
NODE_END = "node_end"          # 节点执行完成
STAGE_CHANGE = "stage_change"  # 工作流阶段变更
```

### 3. Event 类型化辅助方法

添加 `get_typed_data()` 方法，可以根据 `event_type` 自动返回对应的类型化数据模型：

```python
typed_data = event.get_typed_data()
# 根据 event.event_type 返回对应的 Pydantic 模型实例
```

### 4. 团队工作流流式处理实现 (`src/agents/run_agent.py`)

修改 `run_team_agent_with_streaming` 函数，从使用 `team_graph.invoke()` 改为 `team_graph.astream()`：

#### 实现方式

使用 LangGraph 的原生异步流式 API：

1. **astream 异步迭代**：使用 `async for chunk in team_graph.astream()` 直接异步迭代
2. **多模式流式**：使用 `stream_mode=["updates", "messages"]` 同时获取：
   - **updates**: 节点状态更新
   - **messages**: LLM token-by-token 的消息流
3. **实时存储**：每个 chunk 到达时就立即：
   - 创建并存储 NODE_START 事件
   - 提取并存储节点输出的消息
   - 创建并存储 MESSAGE_COMPLETE 事件
   - 创建并存储 LLM_STREAM 事件（增量 token）
   - 检测并存储 STAGE_CHANGE 事件
   - 创建并存储 NODE_END 事件

#### 存储的事件类型

在团队工作流执行过程中会存储以下事件：

- `AGENT_START`: 工作流开始
- `NODE_START`: 每个节点开始执行
- `LLM_STREAM`: LLM 生成的增量 token（实时流式）
- `MESSAGE_COMPLETE`: 每个节点输出的完整消息
- `STAGE_CHANGE`: 工作流阶段变更（requirement → design → development → testing）
- `NODE_END`: 每个节点执行完成
- `AGENT_END`: 工作流成功完成
- `AGENT_ERROR`: 工作流执行出错
- `FINISH`: 工作流结束

#### 存储的消息

每个节点（Boss, PM, Architect, PJM, Engineer, QA）输出的消息都会被存储，包含：
- 消息内容
- 角色（assistant）
- 所属节点/agent
- trace_id（用于关联 Langfuse）

### 5. 优势

相比之前的 `invoke()` 方式：

1. **真正的流式处理**：使用 `astream` 异步迭代器，无需线程和队列
2. **实时性**：在 async for 循环中立即处理和存储，不需要等待整个流程完成
3. **内存效率**：不需要先收集所有 chunks 再处理
4. **LLM 流式输出**：支持 token-by-token 的 LLM 输出捕获
5. **可观察性**：可以实时监控工作流执行进度和 LLM 生成过程
6. **类型安全**：事件数据有明确的类型定义，减少错误
7. **代码简洁**：原生异步支持，代码更简洁易维护

## 使用示例

### 创建类型化事件

```python
from shared.schemas.event import NodeStartData, EventType, Event

# 创建 NODE_START 事件
event = Event(
    event_id="evt_123",
    session_id="sess_456",
    timestamp=time.time(),
    event_type=EventType.NODE_START,
    agent_name="boss",
    data=NodeStartData(
        node_name="boss",
        agent_name="boss"
    ).model_dump(),
)

# 获取类型化数据
typed_data = event.get_typed_data()
assert isinstance(typed_data, NodeStartData)
print(typed_data.node_name)  # "boss"
```

### 监听工作流事件

```python
# 通过 WebSocket 或 SSE 实时接收事件
async for event in event_stream:
    if event.event_type == EventType.NODE_START:
        data = event.get_typed_data()
        print(f"节点 {data.node_name} 开始执行")
    
    elif event.event_type == EventType.LLM_STREAM:
        # 实时接收 LLM 生成的 token
        data = event.get_typed_data()
        print(data.delta, end="", flush=True)
    
    elif event.event_type == EventType.MESSAGE_COMPLETE:
        data = event.get_typed_data()
        print(f"\n收到完整消息: {data.content[:100]}...")
    
    elif event.event_type == EventType.STAGE_CHANGE:
        data = event.get_typed_data()
        print(f"阶段变更: {data.from_stage} → {data.to_stage}")
```

## 后续工作

1. ✅ ~~实现 LLM_STREAM 事件（捕获 LLM 的增量输出）~~ - 已完成
2. 在 API 层实现 SSE（Server-Sent Events）推送事件
3. 优化消息去重逻辑（避免重复存储相同消息）
4. 添加事件过滤和订阅机制
5. 实现 WebSocket 推送支持
6. 添加事件重放功能
