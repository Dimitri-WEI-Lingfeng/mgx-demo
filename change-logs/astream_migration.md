# 迁移到 astream 异步流式 API

## 修改日期
2026-02-02

## 变更概述

将团队工作流的流式处理从同步的 `stream()` + 线程/队列模式迁移到 LangGraph 原生的 `astream()` 异步 API。

## 主要改进

### 之前的实现（使用 stream + 线程）

```python
# ❌ 旧方式：需要线程和队列来桥接同步和异步
import queue
import threading

chunk_queue = queue.Queue()

def run_stream():
    for chunk in team_graph.stream(initial_state):
        chunk_queue.put(("chunk", chunk))

stream_thread = threading.Thread(target=run_stream, daemon=True)
stream_thread.start()

while True:
    event_type, chunk = await asyncio.to_thread(chunk_queue.get, timeout=0.1)
    # 处理 chunk...
```

**缺点：**
- 需要额外的线程管理
- 需要队列来传递数据
- 代码复杂，容易出错
- 只能获取节点级别的更新

### 现在的实现（使用 astream + subgraphs）

```python
# ✅ 新方式：直接使用异步迭代器 + 子图支持
async for chunk in team_graph.astream(
    initial_state,
    stream_mode=["updates", "messages"],
    subgraphs=True,  # 捕获子图中的事件
):
    # 当 subgraphs=True 时，chunk 格式：(namespace, mode, data)
    if len(chunk) == 3:
        namespace, mode, data = chunk  # namespace 是子图路径
    else:
        mode, data = chunk
        namespace = ()
    
    if mode == "updates":
        # 处理节点更新
        for node_name, node_state in data.items():
            # 存储事件和消息（包含 namespace）...
    
    elif mode == "messages":
        # 处理 LLM token 流
        message_chunk, metadata = data
        # 存储 LLM_STREAM 事件（包含 namespace）...
```

**优点：**
- ✅ 原生异步支持，无需线程和队列
- ✅ 代码简洁，逻辑清晰
- ✅ 支持多种流式模式（updates, messages）
- ✅ 可以捕获 LLM token-by-token 的输出
- ✅ 支持子图事件捕获（subgraphs=True）
- ✅ 更好的性能和资源利用

## Stream Mode 说明

### 1. "updates" 模式

返回每个节点执行后的状态更新：

```python
{
    "node_name": {
        "messages": [...],
        "current_stage": "design",
        "prd_document": "...",
        ...
    }
}
```

### 2. "messages" 模式

返回 LLM 生成的每个 token：

```python
(message_chunk, metadata)
# message_chunk.content: "Hello"  # 单个 token 或字符
# metadata: {"langgraph_node": "boss", ...}
```

### 3. 组合使用

使用 `stream_mode=["updates", "messages"]` 可以同时获取两种数据：

```python
async for chunk in team_graph.astream(..., stream_mode=["updates", "messages"]):
    mode, data = chunk
    
    if mode == "updates":
        # 节点级别的完整状态
    elif mode == "messages":
        # LLM token 级别的流式输出
```

### 4. 子图支持 (subgraphs=True)

启用 `subgraphs=True` 后，可以捕获子图（嵌套 Agent）中的事件：

```python
async for chunk in team_graph.astream(
    initial_state,
    stream_mode=["updates", "messages"],
    subgraphs=True,
):
    # chunk 格式：(namespace, mode, data)
    if len(chunk) == 3:
        namespace, mode, data = chunk
        # namespace 示例：("engineer", "code_writer:task_123")
        print(f"事件来自子图路径: {namespace}")
    else:
        mode, data = chunk
        namespace = ()
```

**Namespace 说明：**
- `namespace` 是一个 tuple，表示事件的来源路径
- 例如：`("parent_node", "child_node:task_id")`
- 根节点事件的 namespace 为空 tuple `()`
- 所有事件的 `metadata` 和 `data` 中都会包含 namespace 信息

## 事件存储

### Updates 模式触发的事件

- `NODE_START`: 节点开始执行
- `MESSAGE_COMPLETE`: 节点输出的完整消息
- `STAGE_CHANGE`: 工作流阶段变更
- `NODE_END`: 节点执行完成

### Messages 模式触发的事件

- `LLM_STREAM`: LLM 生成的每个 token（增量）

### 事件中的 Namespace 信息

所有事件都包含 namespace 信息（当 `subgraphs=True` 时）：

```python
{
    "event_type": "NODE_START",
    "data": {
        "node_name": "engineer",
        "agent_name": "engineer",
        "namespace": ["parent_node", "child_node:task_123"]  # 子图路径
    },
    "metadata": {
        "namespace": ["parent_node", "child_node:task_123"]
    }
}
```

## 性能对比

| 指标 | 旧方式（stream + 线程） | 新方式（astream + subgraphs） |
|------|------------------------|------------------------------|
| 代码行数 | ~120 行 | ~85 行 |
| 依赖组件 | queue + threading | 无额外依赖 |
| 内存开销 | 中等（队列缓冲） | 低（直接流式） |
| CPU 开销 | 中等（线程切换） | 低（纯异步） |
| Token 捕获 | ❌ 不支持 | ✅ 支持 |
| 子图事件 | ❌ 不支持 | ✅ 支持 |
| 错误处理 | 复杂 | 简单 |

## 兼容性

- LangGraph >= 0.2.0
- Python >= 3.10（需要 async/await 支持）

## 示例：完整的流式处理（带子图支持）

```python
async def run_team_workflow():
    """运行团队工作流并实时捕获所有事件（包括子图）。"""
    
    async for chunk in team_graph.astream(
        initial_state,
        stream_mode=["updates", "messages"],
        subgraphs=True,  # 启用子图事件捕获
    ):
        # 解析 chunk
        if len(chunk) == 3:
            namespace, mode, data = chunk
            graph_path = " -> ".join(namespace) if namespace else "root"
        else:
            mode, data = chunk
            namespace = ()
            graph_path = "root"
        
        # 处理节点更新
        if mode == "updates":
            for node_name, node_state in data.items():
                print(f"✓ [{graph_path}] {node_name} 完成")
                
                # 存储事件到数据库（包含 namespace）
                await store_node_events(
                    node_name,
                    node_state,
                    namespace=namespace
                )
        
        # 处理 LLM 流式输出
        elif mode == "messages":
            message_chunk, metadata = data
            node_name = metadata.get("langgraph_node")
            
            # 实时显示 LLM 输出（带来源信息）
            print(f"[{graph_path}/{node_name}] ", end="")
            print(message_chunk.content, end="", flush=True)
            
            # 存储 token 到事件流（包含 namespace）
            await store_llm_stream_event(
                node_name,
                message_chunk.content,
                namespace=namespace
            )
```

## 迁移检查清单

- [x] 移除 `import queue` 和 `import threading`
- [x] 将 `team_graph.stream()` 改为 `team_graph.astream()`
- [x] 移除线程创建和队列管理代码
- [x] 使用 `async for` 替代 `while True` 循环
- [x] 添加 `stream_mode` 参数
- [x] 添加 `subgraphs=True` 参数
- [x] 处理多种流式模式（tuple unpacking）
- [x] 处理 namespace（子图路径）
- [x] 实现 LLM_STREAM 事件存储
- [x] 在所有事件中包含 namespace 信息
- [x] 更新文档和示例
- [x] 测试流式输出和事件存储

## 相关文件

- `/Users/feng/codes/mgx-demo/src/agents/run_agent.py` - 主要实现文件
- `/Users/feng/codes/mgx-demo/src/shared/schemas/event.py` - 事件类型定义
- `/Users/feng/codes/mgx-demo/change-logs/streaming_events_implementation.md` - 详细文档
