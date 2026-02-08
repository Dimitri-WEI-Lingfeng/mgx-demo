# message_complete Fallback 逻辑修复

**日期**: 2026-02-08  
**类型**: Bug 修复

## 概述

修复前端 SSE 解析中 `message_complete` 的 fallback 逻辑：当 `message_id` 未在 `prev` 中找到时，错误地用新消息覆盖最后一条，导致 assistant 消息被 tool 消息覆盖，最终只显示 tool 消息。

## 背景

### 问题现象

前端 messages state 中只包含 `role: tool` 的消息，assistant 消息消失。

### 根因

事件流顺序：

1. **delta (content_type: tool_call)**：被 `sse.ts` 忽略（return null），不创建 assistant 消息
2. **message_complete (assistant)**：`message_id` 未在 prev 中找到，fallback 用 assistant 覆盖 lastMsg（如 user）
3. **message_complete (tool)**：`message_id` 未在 prev 中找到，fallback 用 tool 覆盖 lastMsg（assistant）

原 fallback 逻辑：**只要未找到 message_id，就覆盖最后一条消息**。适用于「流式消息用临时 id，message_complete 带着真实 id 更新同一条」的场景，但会错误地处理 tool 消息：tool 是**新消息**，应 append，不应覆盖 assistant。

## 变更内容

### 1. `frontend/src/utils/sse.ts`

调整 `message_complete` 的 fallback 逻辑：

- **更新已有流式消息**：`lastMsg` 存在且 `overwrite.role` 未指定或等于 `lastMsg.role` → 视为完成同一条流式消息，覆盖最后一条
- **追加新消息**：否则（如 tool 消息在 assistant 之后）→ 作为新消息 append，不覆盖

新增 append 分支时，需构造完整 `Message` 对象（含 `session_id`、`timestamp` 等）。

### 2. `frontend/src/utils/sse.test.ts`

新增 2 个用例：

- `handles message_complete - appends when role differs (tool after assistant)`：prev = [assistant]，message_complete 为 tool → 应得到 [assistant, tool]
- `handles message_complete - overwrites last when same role (completing streamed message)`：prev = [assistant(stream-123)]，message_complete 为 assistant → 覆盖最后一条

## 变更文件

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/utils/sse.ts` | 修改 message_complete fallback：按 role 区分覆盖 vs append |
| `frontend/src/utils/sse.test.ts` | 新增 append/覆盖 场景用例 |
