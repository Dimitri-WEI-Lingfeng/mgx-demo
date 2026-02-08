# LangGraph 多 Agent 流式消息研究报告

**日期**: 2026-02-07  
**问题**: 前端 ChatPanel 在 stream 过程中收到的多条 Agent 消息（Boss、PM、Architect 等）被合并成一条展示，未能按节点分开渲染。

---

## 1. LangGraph astream 输出格式

### 1.1 元组结构

在 `stream_mode=["updates", "messages"]` 且 `subgraphs=True` 时，每次迭代输出为 **3 元组**：

```
(namespace, stream_mode, chunk)
```

- **namespace**: `tuple`，当前实验的扁平图（直接节点无子图）下始终为 `()`
- **stream_mode**: `"updates"` 或 `"messages"`
- **chunk**: 根据 stream_mode 不同
  - `updates`: `dict`，如 `{'product_manager': {'messages': [...], ...}}`
  - `messages`: `(message_chunk, metadata)`，其中 `message_chunk` 为 `AIMessageChunk` 或 `AIMessage`，`metadata` 含 `langgraph_node`

### 1.2 messages 模式下的 chunk 结构

```python
# metadata 示例
{
    'langgraph_node': 'boss',           # 或 'product_manager'
    'langgraph_step': 1,
    'langgraph_path': ('__pregel_pull', 'boss'),
    'checkpoint_ns': 'boss:uuid...',
    ...
}
```

### 1.3 message_id 与节点关系

| 节点 | message.id（AIMessageChunk） | 说明 |
|------|------------------------------|------|
| boss | `lc_run--019c3860-4ef2-7aa0-b36b-d46421250233` | 同一节点的所有 chunk 共用 |
| product_manager | `lc_run--019c3860-4ef5-79d3-a2c2-1e4e032d9635` | 不同节点 id 不同 |

**结论**: 不同节点的 `message.id` 不同，可用于区分消息边界。

---

## 2. 事件顺序与消息边界

### 2.1 实际事件顺序（实验 03）

```
1. LLM_STREAM_START (boss, msg_id=xxx)
2-34. LLM_STREAM (boss, delta=...)
35. SKIP - updates（namespace=() 时 run_agent 跳过）
36-51. LLM_STREAM (product_manager, delta=...)
52. SKIP - updates
53. MESSAGE_COMPLETE (boss)  # 实际应为最后一条消息的 node
```

### 2.2 关键发现：namespace=() 时 updates 被跳过

在扁平图（主图节点为普通函数，无子图）下，`namespace` 始终为 `()`。run_agent 中的逻辑：

```python
# run_agent.py 第 476-518 行
if not namespace:
    if not isinstance(chunk, tuple) or len(chunk) != 2:
        continue
    # 只处理 (message, metadata)，对 updates 的 dict 直接 continue 跳过
```

因此 **updates 事件在 namespace=() 时被完全跳过**，不会触发：

- `NODE_START` / `NODE_END`
- 基于 updates 的「保存上一条消息」逻辑

### 2.3 消息合并的根本原因

1. **后端**: 当 PM 的首个 chunk 到达时，`llm_streaming` 仍为 True（Boss 未结束），不会进入「新消息开始」分支，PM 的 delta 被追加到 `current_message_content`，与 Boss 内容合并。
2. **前端**: `llm_stream` 处理时仅判断 `lastMsg.role === 'assistant'` 就追加，未使用 `message_id` 区分不同消息，导致所有 assistant 流式内容合并到同一条消息。

---

## 3. 根因分析

### 3.1 后端 run_agent.py

| 问题 | 位置 | 说明 |
|------|------|------|
| 1. 依赖 updates 切换消息 | 520-565 行 | namespace=() 时 updates 被跳过，无法触发节点切换与消息保存 |
| 2. 未按 message_id 分界 | 630-638 行 | 仅用 `llm_streaming` 标志，未在 `message_chunk.id` 变化时保存上一条并开始新消息 |
| 3. 潜在 stale 引用 | 542-543 行 | `message_chunk` 在 updates 分支中使用，但该变量仅在 messages 分支赋值，可能使用上一轮旧值 |

### 3.2 前端 sse.ts

| 问题 | 位置 | 说明 |
|------|------|------|
| 1. 未校验 message_id | 72-85 行 | 仅 `lastMsg.role === 'assistant'` 就追加 delta，未判断 `lastMsg.message_id === backendMessageId` |

---

## 4. 修复建议

### 4.1 前端 sse.ts（必须）

在 `llm_stream` 的 updater 中，**仅在 message_id 一致时追加**，否则创建新消息：

```typescript
// 修改前
if (lastMsg && lastMsg.role === 'assistant') {
  return [...prev.slice(0, -1), { ...lastMsg, content: lastMsg.content + delta }];
}

// 修改后：需同时满足 message_id 一致
if (lastMsg && lastMsg.role === 'assistant' && 
    (!backendMessageId || lastMsg.message_id === backendMessageId)) {
  return [...prev.slice(0, -1), { ...lastMsg, content: lastMsg.content + delta }];
}
```

`message_complete` 中应通过 `message_id` 定位要更新的消息，而不是默认更新最后一条 assistant 消息。

### 4.2 后端 run_agent.py（必须）

在 messages 分支中，**当 `message_chunk.id` 变化时**，先保存当前消息并发送 `message_complete`，再开始新消息：

```python
# 在 AIMessageChunk 处理中
if isinstance(message_chunk, langchain_messages.AIMessageChunk):
    chunk_msg_id = message_chunk.id or str(uuid.uuid4())
    # 新增：若 message_id 变化，说明切换到了新消息，先保存上一条
    if llm_streaming and chunk_msg_id != current_streaming_message_id:
        # 保存上一条消息，发送 message_complete，重置
        if current_message_content and current_message_node:
            msg = create_message(...)
            await context.message_store.create_message(msg)
            await context.event_store.create_event(message_complete_event)
            current_parent_message_id = _get_message_id(msg)
        current_message_content = ""
        current_message_node = None
        llm_streaming = False

    if not llm_streaming:
        llm_streaming = True
        current_streaming_message_id = chunk_msg_id
        ...
```

### 4.3 后端 run_agent.py（建议）

- 在 updates 分支中保存消息时，避免使用 `message_chunk`（可能未定义或 stale），改为 `tool_calls=None, tool_call_id=None` 或从当前流式上下文中安全获取。
- 评估是否在 namespace=() 时也能处理 updates（例如从 metadata 推断 current_node），以正确发送 `NODE_START`/`NODE_END`。

---

## 5. 实验脚本与复现

| 脚本 | 用途 |
|------|------|
| `experiment_01_astream_format.py` | 打印 astream 原始格式、namespace、chunk 结构 |
| `experiment_02_message_chunk_ids.py` | 验证多节点下 message.id 的变化 |
| `experiment_03_event_order.py` | 模拟 run_agent 逻辑，记录事件时序 |

运行方式：

```bash
uv run python research_langgraph/experiment_01_astream_format.py
uv run python research_langgraph/experiment_02_message_chunk_ids.py
uv run python research_langgraph/experiment_03_event_order.py
```

---

## 6. 总结

| 结论 | 说明 |
|------|------|
| message_id 可区分消息 | 不同节点的 `AIMessageChunk.id` 不同，应作为消息边界依据 |
| 前端必须校验 message_id | 否则会将不同节点的 delta 合并到同一条消息 |
| 后端需按 message_id 分界 | 在 id 变化时保存上一条并开始新消息，不依赖 updates |
| namespace=() 的影响 | 扁平图下 updates 被跳过，不能依赖 node_start/updates 来切换消息 |
