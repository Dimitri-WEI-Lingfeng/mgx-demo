"""消息相关工具函数。"""
import copy
from typing import TYPE_CHECKING

import langchain_core.messages as langchain_messages
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

if TYPE_CHECKING:
    from shared.schemas import Message


def _content_for_langchain(content) -> str | list[dict]:
    """将 Message.content 转为 LangChain 可接受的格式。

    - str: 直接返回
    - list: 若含 ContentPart 或 dict，转为 list[dict]（LangChain content blocks）
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        result = []
        for p in content:
            if isinstance(p, dict):
                result.append(p)
            elif hasattr(p, "model_dump"):
                result.append(p.model_dump())
            elif hasattr(p, "dict"):
                result.append(p.dict())
            else:
                result.append({"type": "text", "text": str(p)})
        return result if result else ""
    return str(content) if content else ""


def _normalize_tool_calls_for_langchain(tool_calls: list | None) -> list[dict]:
    """将 Message.tool_calls 转为 LangChain 格式，确保 args 为 dict。"""
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


def messages_to_langchain(messages: list["Message"]) -> list[langchain_messages.BaseMessage]:
    """将 Message 列表转为 LangChain BaseMessage 格式。

    处理 content（str 与 list）、tool_calls、tool_call_id，并保留 message_id。
    """
    result: list[langchain_messages.BaseMessage] = []
    for msg in messages:
        content = _content_for_langchain(msg.content)
        msg_id = msg.message_id

        if msg.role == "user":
            result.append(HumanMessage(content=content, id=msg_id))
        elif msg.role == "assistant":
            tool_calls = _normalize_tool_calls_for_langchain(msg.tool_calls)
            result.append(
                AIMessage(
                    content=content,
                    tool_calls=tool_calls,
                    id=msg_id,
                )
            )
        elif msg.role == "system":
            result.append(SystemMessage(content=content, id=msg_id))
        elif msg.role == "tool":
            result.append(
                ToolMessage(
                    content=content,
                    tool_call_id=msg.tool_call_id,
                    id=msg_id,
                )
            )
        else:
            result.append(HumanMessage(content=content, id=msg_id))
    return result


def _tool_call_ids_from_msg(msg) -> set[str]:
    """从 AIMessage 提取 tool_call_ids。"""
    tool_calls = getattr(msg, "tool_calls", None) or []
    ids = set()
    for tc in tool_calls:
        tid = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
        if tid:
            ids.add(tid)
    return ids


def _has_complete_tool_responses(
    messages: list[langchain_messages.BaseMessage],
    start_idx: int,
    required_ids: set[str],
) -> bool:
    """检查从 start_idx 开始的后续消息是否包含所有 required_ids 的 ToolMessage。"""
    responded = set()
    for i in range(start_idx + 1, len(messages)):
        m = messages[i]
        if isinstance(m, langchain_messages.ToolMessage):
            tid = getattr(m, "tool_call_id", None)
            if tid:
                responded.add(tid)
        elif isinstance(m, (langchain_messages.HumanMessage, langchain_messages.SystemMessage)):
            break
        elif isinstance(m, (langchain_messages.AIMessage, langchain_messages.AIMessageChunk)):
            break
    return required_ids <= responded


def ensure_messages(
    messages: list[langchain_messages.BaseMessage],
) -> list[langchain_messages.BaseMessage]:
    """确保消息列表满足 LLM API 约束，避免 InternalError.Algo.InvalidParameter。

    1. 移除孤立的 tool 消息（前面没有 assistant+tool_calls 的 tool 消息）
    2. 对未配齐 ToolMessage 响应的 AIMessage(tool_calls)，去掉其 tool_calls 字段
    """
    result: list[langchain_messages.BaseMessage] = []
    last_assistant_had_tool_calls = False

    for i, msg in enumerate(messages):
        msg_type = getattr(msg, "type", None)
        if msg_type == "human" or isinstance(msg, langchain_messages.HumanMessage):
            last_assistant_had_tool_calls = False
            result.append(msg)
        elif msg_type == "system" or isinstance(msg, langchain_messages.SystemMessage):
            last_assistant_had_tool_calls = False
            result.append(msg)
        elif msg_type == "ai" or isinstance(msg, (langchain_messages.AIMessage, langchain_messages.AIMessageChunk)):
            tool_calls = getattr(msg, "tool_calls", None)
            has_tool_calls = bool(tool_calls and len(tool_calls) > 0)
            if has_tool_calls:
                required_ids = _tool_call_ids_from_msg(msg)
                if required_ids and not _has_complete_tool_responses(messages, i, required_ids):
                    # 该 AIMessage 的 tool_calls 未配齐响应，去掉 tool_calls 避免 API 报错
                    msg = copy.deepcopy(msg)
                    if hasattr(msg, "tool_calls"):
                        msg.tool_calls = []
                    has_tool_calls = False
            last_assistant_had_tool_calls = has_tool_calls
            result.append(msg)
        elif msg_type == "tool" or isinstance(msg, langchain_messages.ToolMessage):
            if last_assistant_had_tool_calls:
                result.append(msg)
        else:
            result.append(msg)

    return result
