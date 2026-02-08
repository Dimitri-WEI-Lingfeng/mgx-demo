# Tool Call 流式处理

**日期**: 2026-02-08  
**类型**: 功能增强

## 概述

在前端 SSE 解析中增加对 `content_type: tool_call` 的流式处理，使 tool_call 在流式过程中逐步展示（name、args 逐步累积），与 MESSAGE_COMPLETE 时的最终结果一致。

## 背景

此前 `sse.ts` 对 `content_type: tool_call` 的 LLM_STREAM 事件直接返回 `null`，tool_call 仅在 MESSAGE_COMPLETE 时一次性展示。后端已支持流式发送 tool_call 的 delta（name、args 分块），前端需要同步支持以提升体验。

## 变更内容

### 1. `frontend/src/utils/sse.ts`

- 新增 **tool_call 流式分支**：对 `content_type === 'tool_call'` 的 LLM_STREAM 事件进行流式处理
- **定位消息**：按 `message_id` 查找或创建 assistant 消息（与 text 流相同逻辑）
- **定位 tool_call**：按 `tool_call_index` 在 `tool_calls` 数组中定位或创建条目
- **更新逻辑**：
  - `tool_call_name` 非空时更新 `name`
  - `tool_call_id` 非空时更新 `id`
  - 仅当 delta 为 args（以 `{` 开头）或作为已有 JSON 的 continuation 时，追加到 `args.__raw`
  - name 的 delta 不加入 args

### 2. `frontend/src/components/ChatPanel.tsx`

- **ToolCallBlock** 支持 `args.__raw` 流式展示：
  - 若存在 `__raw`：尝试 `JSON.parse` 美化，失败则原样展示
  - 否则沿用原有 `JSON.stringify(args)` 逻辑

### 3. `frontend/src/utils/sse.test.ts`

新增 4 个用例：

- `handles llm_stream tool_call - creates new message when no assistant`
- `handles llm_stream tool_call - appends args delta to existing message`（含 JSON continuation）
- `handles llm_stream tool_call - appends to existing assistant message`
- `handles message_complete - overwrites streaming __raw with final tool_calls`

## 数据结构约定

- **流式阶段**：`args = { __raw: string }`，`__raw` 为累积的 JSON 字符串
- **完成阶段**：MESSAGE_COMPLETE 会用后端返回的 `tool_calls` 覆盖，`args` 为正常对象

## 变更文件

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/utils/sse.ts` | 新增 tool_call 分支，累积 name/id/args（使用 `__raw`） |
| `frontend/src/components/ChatPanel.tsx` | ToolCallBlock 支持 `args.__raw` 流式展示 |
| `frontend/src/utils/sse.test.ts` | 新增 tool_call 流式与完成的用例 |
