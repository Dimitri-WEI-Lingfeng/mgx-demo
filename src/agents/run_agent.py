"""独立的 agent 运行脚本，在容器中执行。

这个脚本从环境变量读取配置，运行 agent，并将事件写入数据库或内存。

支持两种运行模式：
1. database 模式（默认）：使用数据库存储事件和消息，用于生产环境
2. memory 模式：使用内存存储，用于本地开发和测试
"""

import asyncio
import os
import sys
import time
import traceback
import uuid
from pathlib import Path
import langchain_core.messages as langchain_messages

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.context.base import AgentContext
from shared.config.settings import settings
from shared.schemas import EventType, Event, Message
from shared.schemas.event import (
    AgentStartData,
    AgentEndData,
    AgentErrorData,
    NodeStartData,
    NodeEndData,
    StageChangeData,
    MessageCompleteData,
    LLMStreamData,
    FinishData,
)
from agents.agent_factory import create_code_generation_agent, create_team_agent
from agents.utils import ensure_messages
from agents.web_app_team.state import create_initial_state
from agents.context import (
    InMemoryContext,
    DatabaseContext,
    set_context,
    clear_context,
)
from shared.agent_stop_signal import is_stop_requested


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


def _get_message_id(msg) -> str:
    """从 Message 或 LangChain BaseMessage 安全获取 message_id。

    LangChain 消息使用 `id` 属性，我们的 Message schema 使用 `message_id`。
    """
    return getattr(msg, "message_id", None) or getattr(msg, "id", None) or str(uuid.uuid4())


def _get_content_for_event(msg: Message) -> str:
    """从 Message 提取用于 MESSAGE_COMPLETE 事件的 content 字符串。"""
    c = msg.content
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        texts = []
        for p in c:
            if isinstance(p, dict) and p.get("type") == "text":
                texts.append(p.get("text", "") or "")
            elif hasattr(p, "text") and p.text:
                texts.append(p.text)
        return " ".join(texts) if texts else ""
    return str(c) if c else ""


def _normalize_tool_calls(tool_calls) -> list[dict]:
    """Convert LangChain tool_calls to Message schema format."""
    if not tool_calls:
        return []
    result = []
    for tc in tool_calls:
        if isinstance(tc, dict):
            result.append({
                "type": "tool_call",
                "id": tc.get("id"),
                "name": tc.get("name"),
                "args": tc.get("args") or {},
            })
        else:
            result.append({
                "type": "tool_call",
                "id": getattr(tc, "id", None),
                "name": getattr(tc, "name", None),
                "args": getattr(tc, "args", None) or {},
            })
    return result


def create_message(
    session_id: str,
    role: str,
    content: str | list[str | dict],
    tool_calls: list[langchain_messages.ToolCall] | None = None,
    tool_call_id: str | None = None,
    trace_id: str | None = None,
    agent_name: str | None = None,
    parent_id: str | None = None,
    message_id: str | None = None,
) -> Message:
    """创建 Message 实例的辅助函数。

    Args:
        session_id: 会话 ID
        role: 消息角色
        content: 消息内容
        trace_id: 追踪 ID
        agent_name: Agent 名称
        parent_id: 父消息 ID（用于构建消息树）
        message_id: 可选，若提供则使用（用于 chunk 流式场景与 store 保持一致）

    Returns:
        Message 实例
    """

    normalized_tool_calls = _normalize_tool_calls(tool_calls) if tool_calls else []
    return Message(
        message_id=message_id or str(uuid.uuid4()),
        session_id=session_id,
        role=role,
        content=content,
        timestamp=time.time(),
        trace_id=trace_id,
        agent_name=agent_name,
        parent_id=parent_id,
        tool_calls=normalized_tool_calls,
        tool_call_id=tool_call_id,
    )


async def run_agent_with_streaming(
    context: AgentContext,
    framework: str,
    prompt: str,
    trace_id: str | None = None,
    last_message_id: str | None = None,
    last_user_msg: Message | None = None,
):
    """运行 agent 并写入流式事件。

    Args:
        context: AgentContext 实例
        framework: 目标框架
        prompt: 用户提示词（从历史消息获取）
        trace_id: 可选的 langfuse trace ID
        last_message_id: 上一条消息的 ID（用于构建消息链）
        last_user_msg: API 层已创建的用户消息（用于事件关联，不重复存储）

    Returns:
        dict: 结果包含状态和修改的文件
    """
    # 设置上下文
    set_context(context)

    session_id = context.session_id
    workspace_id = context.workspace_id

    # 用户消息：API 层已创建时用 last_user_msg；否则创建并存储（memory 模式 / 测试）
    if last_user_msg is not None:
        user_msg = last_user_msg
    else:
        user_msg = create_message(
            session_id=session_id,
            role="user",
            content=prompt,
            trace_id=trace_id,
            agent_name=None,
            parent_id=last_message_id,
        )
        await context.message_store.create_message(user_msg)
        evt = create_event(
            session_id=session_id,
            event_type=EventType.MESSAGE_COMPLETE,
            data={"content": prompt},
            message_id=_get_message_id(user_msg),
            trace_id=trace_id,
            agent_name=None,
        )
        await context.event_store.create_event(evt)

    # 发送 agent_start 事件（携带 user message_id）
    event = create_event(
        session_id=session_id,
        event_type=EventType.AGENT_START,
        data={"prompt": prompt, "framework": framework},
        message_id=_get_message_id(user_msg) if user_msg else None,
        trace_id=trace_id,
        agent_name="code_generation_agent",
    )
    await context.event_store.create_event(event)

    try:
        # 初始化 langfuse callback（如果启用）
        callbacks = []
        if settings.langfuse_enabled and settings.langfuse_public_key:
            try:
                from langfuse.callback import CallbackHandler as LangfuseCallbackHandler

                langfuse_handler = LangfuseCallbackHandler(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                    session_id=session_id,
                    tags=["agent", "code_generation", framework],
                    metadata={
                        "workspace_id": workspace_id,
                        "framework": framework,
                    },
                )
                callbacks.append(langfuse_handler)

                # 更新 trace_id
                if not trace_id and hasattr(langfuse_handler, "trace_id"):
                    trace_id = langfuse_handler.trace_id

            except Exception as e:
                # Langfuse 是可选的，继续执行
                print(f"Failed to initialize langfuse: {e}")
                traceback.print_exc()

        # 创建 agent
        agent = create_code_generation_agent(framework, callbacks=callbacks)

        # 使用 invoke 执行 agent
        # TODO: 实现真正的流式支持
        result = await asyncio.to_thread(agent.invoke, {"input": prompt}, {"callbacks": callbacks})

        # 提取输出
        output = result.get("output", "")

        # 保存助手消息（引用用户消息作为 parent）
        msg = create_message(
            session_id=session_id,
            role="assistant",
            content=output,
            trace_id=trace_id,
            agent_name="code_generation_agent",
            parent_id=_get_message_id(user_msg) if user_msg else None,
        )
        await context.message_store.create_message(msg)

        event = create_event(
            session_id=session_id,
            event_type=EventType.MESSAGE_COMPLETE,
            data={"content": output},
            message_id=_get_message_id(msg),
            trace_id=trace_id,
            agent_name="code_generation_agent",
        )
        await context.event_store.create_event(event)

        # 发送 agent_end 事件
        event = create_event(
            session_id=session_id,
            event_type=EventType.AGENT_END,
            data={"status": "success", "output": output},
            trace_id=trace_id,
            agent_name="code_generation_agent",
        )
        await context.event_store.create_event(event)

        # 发送 finish 事件
        event = create_event(
            session_id=session_id,
            event_type=EventType.FINISH,
            data={"status": "success"},
            trace_id=trace_id,
            agent_name="code_generation_agent",
        )
        await context.event_store.create_event(event)

        # 刷新 langfuse 事件
        if callbacks:
            for callback in callbacks:
                if hasattr(callback, "flush"):
                    callback.flush()

        return {
            "session_id": session_id,
            "workspace_id": workspace_id,
            "status": "success",
            "output": output,
            "changed_files": [],  # TODO: 跟踪修改的文件
        }

    except Exception as e:
        print(f"Error in code generation agent: {e}")
        traceback.print_exc()
        # 发送错误事件
        event = create_event(
            session_id=session_id,
            event_type=EventType.AGENT_ERROR,
            data={"error": str(e), "error_type": type(e).__name__, "details": traceback.format_exc()},
            trace_id=trace_id,
            agent_name="code_generation_agent",
        )
        await context.event_store.create_event(event)

        # 发送 finish 事件（错误状态）
        event = create_event(
            session_id=session_id,
            event_type=EventType.FINISH,
            data={"status": "error", "error": str(e)},
            trace_id=trace_id,
            agent_name="code_generation_agent",
        )
        await context.event_store.create_event(event)

        # 即使出错也刷新 langfuse 事件
        if callbacks:
            for callback in callbacks:
                if hasattr(callback, "flush"):
                    callback.flush()

        return {
            "session_id": session_id,
            "workspace_id": workspace_id,
            "status": "failed",
            "error": str(e),
            "changed_files": [],
        }


async def run_team_agent_with_streaming(
    context: AgentContext,
    framework: str,
    prompt: str | None = None,
    trace_id: str | None = None,
    last_message_id: str | None = None,
    last_user_msg: Message | None = None,
):
    """运行团队 agent 并写入流式事件。

    Args:
        context: AgentContext 实例
        framework: 目标框架
        prompt: 用户提示词（从历史消息获取）
        trace_id: 可选的 langfuse trace ID
        last_message_id: 上一条消息的 ID（用于构建消息链）
        last_user_msg: API 层已创建的用户消息（用于事件关联，不重复存储）

    Returns:
        dict: 结果包含状态和修改的文件
    """
    # 设置上下文
    set_context(context)

    session_id = context.session_id
    workspace_id = context.workspace_id

    # 用户消息：API 层已创建时用 last_user_msg；否则创建并存储（memory 模式 / 测试）
    if last_user_msg is not None:
        user_msg = last_user_msg
    else:
        if prompt is None:
            print("Error: prompt is None")
            return
        user_msg = create_message(
            session_id=session_id,
            role="user",
            content=prompt,
            trace_id=trace_id,
            agent_name=None,
            parent_id=last_message_id,
        )
        await context.message_store.create_message(user_msg)
        evt = create_event(
            session_id=session_id,
            event_type=EventType.MESSAGE_COMPLETE,
            data={"content": prompt},
            message_id=_get_message_id(user_msg),
            trace_id=trace_id,
            agent_name=None,
        )
        await context.event_store.create_event(evt)

    # 确定用于 event 的 prompt 文本（当 API 层传入 last_user_msg 时 prompt 可能为 None）
    prompt_for_event = prompt
    if prompt_for_event is None and user_msg is not None:
        c = user_msg.content
        if isinstance(c, str):
            prompt_for_event = c
        elif isinstance(c, list):
            texts = []
            for p in c:
                if isinstance(p, dict) and p.get("type") == "text":
                    texts.append(p.get("text", "") or "")
                elif hasattr(p, "text") and p.text:
                    texts.append(p.text)
            prompt_for_event = " ".join(texts) if texts else ""
        else:
            prompt_for_event = ""

    # 发送 agent_start 事件（携带 user message_id）
    event = create_event(
        session_id=session_id,
        event_type=EventType.AGENT_START,
        data={"prompt": prompt_for_event or "", "framework": framework, "mode": "team"},
        message_id=_get_message_id(user_msg) if user_msg else None,
        trace_id=trace_id,
        agent_name="team_agent",
    )
    await context.event_store.create_event(event)

    try:
        # 初始化 langfuse callback（如果启用）
        callbacks = []
        if settings.langfuse_enabled and settings.langfuse_public_key:
            try:
                from langfuse.callback import CallbackHandler as LangfuseCallbackHandler

                langfuse_handler = LangfuseCallbackHandler(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                    session_id=session_id,
                    tags=["agent", "team", "web_app_development", framework],
                    metadata={
                        "workspace_id": workspace_id,
                        "framework": framework,
                        "mode": "team",
                    },
                )
                callbacks.append(langfuse_handler)

                if not trace_id and hasattr(langfuse_handler, "trace_id"):
                    trace_id = langfuse_handler.trace_id

            except Exception as e:
                print(f"Failed to initialize langfuse: {e}")
                traceback.print_exc()

        # 创建团队 agent
        team_graph = create_team_agent(
            framework=framework,
            callbacks=callbacks,
        )

        # 加载历史消息
        # last_user_msg 不为 None：查 last_user_msg 之前的 n 条
        # last_message_id 为 None：查询最近的 n 条；不为 None：查询从 last_message_id 开始的 n 条
        history_messages: list[langchain_messages.BaseMessage] = []
        n = 100  # 限制历史消息数量

        from agents.context.database import DatabaseMessageStore

        if isinstance(context.message_store, DatabaseMessageStore):
            if last_user_msg is not None:
                print(f"\n加载历史消息（last_user_msg 之前的 {n} 条）...")
                messages = await context.message_store.dao.get_session_messages_paginated(
                    session_id=session_id,
                    limit=n,
                    before_message_id=_get_message_id(last_user_msg),
                )
            elif last_message_id is None:
                print(f"\n加载历史消息（最近 {n} 条）...")
                messages = await context.message_store.dao.get_session_messages_paginated(
                    session_id=session_id,
                    limit=n,
                    last_message_id=None,
                )
            else:
                print(f"\n加载历史消息（从 last_message_id: {last_message_id} 开始，共 {n} 条）...")
                messages = await context.message_store.dao.get_session_messages_paginated(
                    session_id=session_id,
                    limit=n,
                    last_message_id=last_message_id,
                )

            # 转换为 LangChain 消息格式
            from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

            for msg in messages:
                if msg.role == "user":
                    history_messages.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    history_messages.append(
                        AIMessage(
                            content=msg.content,
                            tool_calls=(
                                [
                                    {
                                        "type": "tool_call",
                                        "id": tool_call.get("id"),
                                        "name": tool_call.get("name"),
                                        "args": tool_call.get("args"),
                                    }
                                    for tool_call in msg.tool_calls
                                ]
                                if msg.tool_calls is not None
                                else []
                            ),
                        )
                    )
                elif msg.role == "system":
                    history_messages.append(SystemMessage(content=msg.content))
                elif msg.role == "tool":
                    history_messages.append(ToolMessage(content=msg.content, tool_call_id=msg.tool_call_id))

            history_messages = ensure_messages(history_messages)
            print(f"  已加载 {len(history_messages)} 条历史消息")

        # 创建初始状态（使用 prompt_for_event，API 层传入 last_user_msg 时 prompt 可能为 None）
        initial_state = create_initial_state(
            workspace_id=workspace_id,
            framework=framework,
            user_prompt=prompt_for_event or "",
            history_messages=history_messages if history_messages else None,
        )

        # 执行团队工作流（使用 astream）
        print(f"\n开始执行团队工作流...")

        current_stage = None
        last_node = None
        llm_streaming = False  # 跟踪是否正在流式输出 LLM tokens

        # 消息追踪：用单个 AIMessageChunk 累积流式输出，避免零碎变量
        current_chunk: langchain_messages.AIMessageChunk | None = None
        current_message_node: str | None = None  # 当前消息所属节点（用于 agent_name）
        current_parent_message_id = _get_message_id(user_msg) if user_msg else None

        async def _save_chunk_and_reset(chunk: langchain_messages.AIMessageChunk | None) -> None:
            """将累积的 chunk 保存为 Message 并重置。"""
            nonlocal current_chunk, current_message_node, current_parent_message_id
            if not chunk or not current_message_node:
                return
            content = chunk.text if chunk.content else ""
            if not content and not getattr(chunk, "tool_calls", None):
                return
            msg = create_message(
                session_id=session_id,
                role="assistant",
                content=content,
                trace_id=trace_id,
                agent_name=current_message_node,
                parent_id=current_parent_message_id,
                message_id=getattr(chunk, "id", None),
                tool_calls=getattr(chunk, "tool_calls", None) or [],
                tool_call_id=None,
            )
            await context.message_store.create_message(msg)
            evt = create_event(
                session_id=session_id,
                event_type=EventType.MESSAGE_COMPLETE,
                data={"content": content},
                message_id=msg.message_id,
                trace_id=trace_id,
                agent_name=current_message_node,
            )
            await context.event_store.create_event(evt)
            current_parent_message_id = msg.message_id
            current_chunk = None
            current_message_node = None

        # 使用 astream 方法异步流式获取更新并立即处理
        # stream_mode 使用 ["updates", "messages"] 来同时获取节点更新和 LLM 消息
        # subgraphs=True 可以捕获子图中的事件
        parent_message_id = last_message_id
        stopped_by_request = False
        async for stream_output in team_graph.astream(
            initial_state,
            stream_mode=["updates", "messages"],
            subgraphs=True,
        ):
            # 检查是否收到停止信号（Redis），若有则保存当前内容后退出
            if await asyncio.to_thread(is_stop_requested, session_id):
                print("\n收到停止信号，保存内容后退出...")
                stopped_by_request = True
                break

            assert len(stream_output) == 3
            namespace, stream_mode, chunk = stream_output
            if not namespace:
                if stream_mode == "updates":
                    continue
                if not isinstance(chunk, tuple) or len(chunk) != 2:
                    continue
                message, metadata = chunk
                node_name = metadata.get("langgraph_node") or "unknown"
                # AIMessageChunk：设置 current_node 后 fall through 到主逻辑的 messages 分支进行累积
                if isinstance(message, langchain_messages.AIMessageChunk):
                    current_node = node_name.split(":")[0] if node_name else "unknown"
                    # 不 continue，fall through 到下方 stream_mode=="messages" 分支统一处理
                elif isinstance(message, langchain_messages.BaseMessage):
                    msg = None
                    if isinstance(message, langchain_messages.AIMessage):
                        msg = create_message(
                            session_id=session_id,
                            role="assistant",
                            content=message.content,
                            trace_id=trace_id,
                            agent_name=node_name,
                            parent_id=parent_message_id,
                            tool_calls=getattr(message, "tool_calls", None) or [],
                            tool_call_id=None,
                        )
                    elif isinstance(message, langchain_messages.SystemMessage):
                        msg = create_message(
                            session_id=session_id,
                            role="system",
                            content=message.content,
                            trace_id=trace_id,
                            agent_name=node_name,
                            parent_id=parent_message_id,
                        )
                    elif isinstance(message, langchain_messages.ToolMessage):
                        # 先保存累积的 AIMessageChunk（含 tool_calls），再存 ToolMessage
                        await _save_chunk_and_reset(current_chunk)
                        llm_streaming = False
                        msg = create_message(
                            session_id=session_id,
                            role="tool",
                            content=message.content,
                            trace_id=trace_id,
                            agent_name=node_name,
                            parent_id=current_parent_message_id or parent_message_id,
                            tool_calls=None,
                            tool_call_id=getattr(message, "tool_call_id", None),
                        )
                    if msg is not None:
                        await context.message_store.create_message(msg)
                        evt = create_event(
                            session_id=session_id,
                            event_type=EventType.MESSAGE_COMPLETE,
                            data={"content": _get_content_for_event(msg)},
                            message_id=msg.message_id,
                            trace_id=trace_id,
                            agent_name=node_name,
                        )
                        await context.event_store.create_event(evt)
                        parent_message_id = _get_message_id(msg)
                        current_parent_message_id = _get_message_id(msg)
                    continue
                else:
                    print(f"  未知消息类型: {type(message)}")
                    print(f"  消息内容: {message}")
                    continue
            else:
                current_node = namespace[0].split(":")[0]

            # 处理 "updates" 模式：节点更新
            if stream_mode == "updates":
                # chunk 是节点的输出状态
                node_output = chunk

                # 如果之前在流式输出 LLM tokens，标记结束
                if llm_streaming:
                    llm_streaming = False

                # 处理节点变化
                if current_node != last_node:
                    if last_node:
                        # 保存上一个节点的完整消息（如果有）
                        await _save_chunk_and_reset(current_chunk)

                        # 上一个节点结束
                        node_end_event = create_event(
                            session_id=session_id,
                            event_type=EventType.NODE_END,
                            data={"node_name": last_node},
                            trace_id=trace_id,
                            agent_name=last_node,
                        )
                        await context.event_store.create_event(node_end_event)

                    # 新节点开始
                    node_start_event = create_event(
                        session_id=session_id,
                        event_type=EventType.NODE_START,
                        data={"node_name": current_node},
                        trace_id=trace_id,
                        agent_name=current_node,
                    )
                    await context.event_store.create_event(node_start_event)
                    last_node = current_node

                # 检查阶段变化
                if isinstance(node_output, dict) and "current_stage" in node_output:
                    new_stage = node_output["current_stage"]
                    if new_stage and new_stage != current_stage:
                        # 发送阶段变化事件
                        stage_change_event = create_event(
                            session_id=session_id,
                            event_type=EventType.STAGE_CHANGE,
                            data={
                                "old_stage": current_stage,
                                "new_stage": new_stage,
                            },
                            trace_id=trace_id,
                            agent_name=current_node,
                        )
                        await context.event_store.create_event(stage_change_event)
                        current_stage = new_stage

                # 保存最后的结果
                if isinstance(node_output, dict):
                    final_result = node_output

            # 处理 "messages" 模式：LLM 消息流（token-by-token）
            elif stream_mode == "messages":
                # chunk 是一个 tuple: (message_chunk, metadata)
                # 添加防御性检查
                if not isinstance(chunk, tuple) or len(chunk) != 2:
                    print(
                        f"  警告: messages 模式下 chunk 格式不正确: {type(chunk)}, len={len(chunk) if isinstance(chunk, (tuple, list)) else 'N/A'}"
                    )
                    continue

                message_chunk, metadata = chunk

                # 检查 metadata 是否为 dict
                if not isinstance(metadata, dict):
                    print(f"  警告: metadata 不是 dict: {type(metadata)}")
                    metadata = {}

                # 提取 node 信息
                node_name = metadata.get("langgraph_node", current_node or "unknown")

                # 根据消息类型进行不同的处理
                if isinstance(message_chunk, langchain_messages.AIMessageChunk):
                    # 处理 AI 消息流（增量）：用单个 AIMessageChunk 累积
                    chunk_msg_id = message_chunk.id or str(uuid.uuid4())
                    # message_id 变化说明切换到新消息，先保存上一条
                    if llm_streaming and current_chunk and chunk_msg_id != getattr(current_chunk, "id", None):
                        await _save_chunk_and_reset(current_chunk)
                        llm_streaming = False

                    if not llm_streaming:
                        llm_streaming = True
                        current_chunk = message_chunk
                        current_message_node = node_name
                    else:
                        # 合并 chunk（LangChain 支持 + 操作符）
                        current_chunk = current_chunk + message_chunk

                    chunk_text = message_chunk.text if message_chunk.content else ""
                    # 发送 LLM_STREAM 事件（增量消息，必须带 message_id）
                    if chunk_text:
                        llm_stream_event = create_event(
                            session_id=session_id,
                            event_type=EventType.LLM_STREAM,
                            data={
                                "delta": chunk_text,
                                "content_type": "text",
                                "namespace": list(namespace) if namespace else None,
                            },
                            message_id=chunk_msg_id,
                            trace_id=trace_id,
                            agent_name=node_name,
                        )
                        llm_stream_event.metadata["namespace"] = list(namespace) if namespace else None
                        await context.event_store.create_event(llm_stream_event)

                    # 处理 tool_call_chunks：流式发送 tool call 增量
                    tool_call_chunks = getattr(message_chunk, "tool_call_chunks", None) or []
                    for tc in tool_call_chunks:
                        # delta 优先用 args（JSON 片段），其次用 name
                        delta = tc.get("args") or tc.get("name") or ""
                        if not delta:
                            continue
                        llm_stream_event = create_event(
                            session_id=session_id,
                            event_type=EventType.LLM_STREAM,
                            data={
                                "delta": delta,
                                "content_type": "tool_call",
                                "namespace": list(namespace) if namespace else None,
                                "tool_call_id": tc.get("id"),
                                "tool_call_index": tc.get("index"),
                                "tool_call_name": tc.get("name"),
                            },
                            message_id=chunk_msg_id,
                            trace_id=trace_id,
                            agent_name=node_name,
                        )
                        llm_stream_event.metadata["namespace"] = list(namespace) if namespace else None
                        await context.event_store.create_event(llm_stream_event)

                elif isinstance(message_chunk, langchain_messages.ToolMessage):
                    # 处理工具消息：先保存当前累积的 assistant 消息，再存储 ToolMessage
                    await _save_chunk_and_reset(current_chunk)
                    llm_streaming = False
                    tool_msg = create_message(
                        session_id=session_id,
                        role="tool",
                        content=message_chunk.content,
                        trace_id=trace_id,
                        agent_name=node_name,
                        parent_id=current_parent_message_id,
                        tool_calls=None,
                        tool_call_id=getattr(message_chunk, "tool_call_id", None),
                    )
                    await context.message_store.create_message(tool_msg)
                    evt = create_event(
                        session_id=session_id,
                        event_type=EventType.MESSAGE_COMPLETE,
                        data={"content": _get_content_for_event(tool_msg)},
                        message_id=tool_msg.message_id,
                        trace_id=trace_id,
                        agent_name=node_name,
                    )
                    await context.event_store.create_event(evt)
                    current_parent_message_id = tool_msg.message_id
                    parent_message_id = tool_msg.message_id

                elif isinstance(message_chunk, langchain_messages.AIMessage):
                    # 处理完整的 AI 消息（非流式，含 tool_calls）
                    await _save_chunk_and_reset(current_chunk)
                    llm_streaming = False
                    ai_msg = create_message(
                        session_id=session_id,
                        role="assistant",
                        content=message_chunk.content or "",
                        trace_id=trace_id,
                        agent_name=node_name,
                        parent_id=current_parent_message_id,
                        tool_calls=getattr(message_chunk, "tool_calls", None) or [],
                        tool_call_id=None,
                        message_id=getattr(message_chunk, "id", None),
                    )
                    await context.message_store.create_message(ai_msg)
                    evt = create_event(
                        session_id=session_id,
                        event_type=EventType.MESSAGE_COMPLETE,
                        data={"content": _get_content_for_event(ai_msg)},
                        message_id=ai_msg.message_id,
                        trace_id=trace_id,
                        agent_name=node_name,
                    )
                    await context.event_store.create_event(evt)
                    current_parent_message_id = ai_msg.message_id
                    parent_message_id = ai_msg.message_id

                elif isinstance(message_chunk, langchain_messages.BaseMessage):
                    # 其他 BaseMessage 子类（如 ChatMessage 等）
                    await _save_chunk_and_reset(current_chunk)
                    llm_streaming = False
                    role = getattr(message_chunk, "type", "assistant")
                    if role == "human":
                        role = "user"
                    elif role not in ("system", "tool"):
                        role = "assistant"
                    other_msg = create_message(
                        session_id=session_id,
                        role=role,
                        content=getattr(message_chunk, "content", ""),
                        trace_id=trace_id,
                        agent_name=node_name,
                        parent_id=current_parent_message_id,
                    )
                    await context.message_store.create_message(other_msg)
                    evt = create_event(
                        session_id=session_id,
                        event_type=EventType.MESSAGE_COMPLETE,
                        data={"content": _get_content_for_event(other_msg)},
                        message_id=other_msg.message_id,
                        trace_id=trace_id,
                        agent_name=node_name,
                    )
                    await context.event_store.create_event(evt)
                    current_parent_message_id = other_msg.message_id
                    parent_message_id = other_msg.message_id

                else:
                    print(f"  未知消息类型: {type(message_chunk)}")
                    print(f"  消息内容: {message_chunk}")

        # 保存最后一个节点的完整消息（如果有）
        await _save_chunk_and_reset(current_chunk)

        # 最后一个节点结束
        if last_node:
            node_end_event = create_event(
                session_id=session_id,
                event_type=EventType.NODE_END,
                data={"node_name": last_node},
                trace_id=trace_id,
                agent_name=last_node,
            )
            await context.event_store.create_event(node_end_event)

        # 发送 agent_end 事件
        agent_end_event = create_event(
            session_id=session_id,
            event_type=EventType.AGENT_END,
            data={"status": "success"},
            trace_id=trace_id,
            agent_name="team_agent",
        )
        await context.event_store.create_event(agent_end_event)

        # 发送 finish 事件
        finish_status = "stopped" if stopped_by_request else "success"
        event = create_event(
            session_id=session_id,
            event_type=EventType.FINISH,
            data={"status": finish_status},
            trace_id=trace_id,
            agent_name="team_agent",
        )
        await context.event_store.create_event(event)

        # 刷新 langfuse 事件
        if callbacks:
            for callback in callbacks:
                if hasattr(callback, "flush"):
                    callback.flush()

        return {
            "session_id": session_id,
            "workspace_id": workspace_id,
            "status": finish_status,
            "changed_files": [],  # TODO: 跟踪修改的文件
        }

    except Exception as e:
        error_details = traceback.format_exc()
        # 提取 ExceptionGroup 中的真实子异常（TaskGroup 会把异常包装成 ExceptionGroup）
        real_error = str(e)
        real_error_type = type(e).__name__
        if hasattr(e, "exceptions") and e.exceptions:
            sub = e.exceptions[0]
            real_error = f"{real_error} | 实际异常: {type(sub).__name__}: {sub}"
            real_error_type = f"{real_error_type}({type(sub).__name__})"
        print(f"Error in team agent: {error_details}")
        print(f"  Real sub-exception: {real_error}")

        # 发送错误事件
        event = create_event(
            session_id=session_id,
            event_type=EventType.AGENT_ERROR,
            data={"error": real_error, "error_type": real_error_type, "details": error_details},
            trace_id=trace_id,
            agent_name="team_agent",
        )
        await context.event_store.create_event(event)

        # 发送 finish 事件（错误状态）
        event = create_event(
            session_id=session_id,
            event_type=EventType.FINISH,
            data={"status": "error", "error": real_error},
            trace_id=trace_id,
            agent_name="team_agent",
        )
        await context.event_store.create_event(event)

        # 即使出错也刷新 langfuse 事件
        if callbacks:
            for callback in callbacks:
                if hasattr(callback, "flush"):
                    callback.flush()

        return {
            "session_id": session_id,
            "workspace_id": workspace_id,
            "status": "failed",
            "error": real_error,
            "changed_files": [],
        }


async def main():
    """主入口函数，从环境变量读取参数并运行 agent。"""
    # 从环境变量读取参数
    framework = os.environ.get("FRAMEWORK")
    trace_id = os.environ.get("TRACE_ID")
    last_message_id = os.environ.get("LAST_MESSAGE_ID")  # 可选的上一条消息 ID

    # 决定运行模式：database（默认）或 memory
    agent_mode = os.environ.get("AGENT_MODE", "team")  # team or single

    # 数据库模式：用于生产环境
    session_id = os.environ.get("SESSION_ID")
    workspace_id = os.environ.get("WORKSPACE_ID")

    if not all([session_id, workspace_id]):
        print("Error: Missing required environment variables for database mode")
        print(f"  SESSION_ID: {session_id}")
        print(f"  WORKSPACE_ID: {workspace_id}")
        sys.exit(1)

    if not framework:
        print("Error: Missing required environment variable FRAMEWORK")
        sys.exit(1)

    context = DatabaseContext(
        session_id=session_id,
        workspace_id=workspace_id,
    )

    # 从历史消息获取 prompt：最后一条必须为 user 消息才运行 agent
    messages = await context.message_store.dao.get_session_messages_paginated(
        session_id=session_id,
        limit=1,
        last_message_id=None,
    )
    if not messages or messages[-1].role != "user":
        print("Skip: Last message is not user message, agent will not run")
        return
    
    last_user_msg = messages[-1]  # 用于事件关联，API 已存储

    print(f"  Agent Mode: {agent_mode}")
    print(f"  Session: {context.session_id}")
    print(f"  Workspace: {context.workspace_id}")
    print(f"  Framework: {framework}")
    if last_message_id:
        print(f"  Last Message ID: {last_message_id}")

    try:
        # 根据模式运行不同的 agent
        if agent_mode == "team":
            result = await run_team_agent_with_streaming(
                context=context,
                framework=framework,
                prompt=None,
                trace_id=trace_id,
                last_message_id=last_message_id,
                last_user_msg=last_user_msg,
            )
        else:
            result = await run_agent_with_streaming(
                context=context,
                framework=framework,
                prompt=prompt,
                trace_id=trace_id,
                last_message_id=last_message_id,
                last_user_msg=last_user_msg,
            )

        print(f"\nAgent completed with status: {result['status']}")

        # 如果失败（非 success 且非 stopped），返回非零退出码
        if result["status"] not in ("success", "stopped"):
            sys.exit(1)

    finally:
        # 清除上下文
        clear_context()


if __name__ == "__main__":
    asyncio.run(main())
