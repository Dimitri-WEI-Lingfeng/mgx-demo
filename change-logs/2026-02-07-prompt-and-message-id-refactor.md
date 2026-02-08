# 2026-02-07: Prompt 与 create_event 重构

## 概述

1. **Prompt 重构**：从历史消息获取 prompt，仅当最后一条消息为 user 时才运行 agent；user 消息在 API 层创建
2. **create_event 重构**：有 message 或 chunk 的事件必须传入 message_id；chunk 无 message 时在首 chunk 时生成 id，并在 store message 时复用

## 变更详情

### API 层 (src/mgx_api/api/agent.py)

- 在 `generate_stream` 中，提交 Celery 任务**前**创建并存储 user 消息
- 使用 `MessageDAO` 创建 `role="user"`, `content=body.prompt` 的消息
- 任务签名改为 `run_team_agent_for_web_app_development.delay(session_id, workspace_id, framework)`，不再传递 prompt

### Scheduler 层 (src/scheduler/tasks.py)

- `create_agent_container`：移除 `prompt` 参数，不再设置 `PROMPT` 环境变量
- `run_team_agent_for_web_app_development`：移除 `prompt` 参数

### Agent 层 (src/agents/run_agent.py)

- `main()`：从 `get_session_messages_paginated(limit=1)` 获取最后一条消息
  - 若为空或 `role != "user"`：直接 return，不执行 agent
  - 否则：`prompt = messages[-1].content`，继续执行
- 用户消息：API 层已创建时使用 `last_user_msg`；否则创建并存储（memory 模式 / 测试 fallback）
- `create_message`：新增 `message_id` 可选参数，支持预生成 id（用于 chunk 流式场景）
- **AGENT_START**：添加 `message_id=_get_message_id(user_msg)`
- **LLM_STREAM**：首 chunk 时生成 `current_streaming_message_id`，所有 LLM_STREAM 事件携带该 `message_id`
- **MESSAGE_COMPLETE**：保存消息时使用 `create_message(..., message_id=current_streaming_message_id)` 确保 id 一致

## 数据流

```
Client -> API: POST /generate {prompt}
API -> DB: create user message
API -> Celery: run_team_agent(session_id, workspace_id, framework)  # 无 prompt
Celery -> Container: env 无 PROMPT
Container -> DB: get last message
Container: if last.role != user then return
Container: prompt = last.content, run agent
```

## 验证

- 所有 pytest 通过
- API 调用后 messages 表应有 user 消息
- LLM_STREAM 与 MESSAGE_COMPLETE 的 message_id 一致
