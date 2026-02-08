"""消息相关工具函数。"""
import langchain_core.messages as langchain_messages


def ensure_messages(
    messages: list[langchain_messages.BaseMessage],
) -> list[langchain_messages.BaseMessage]:
    """确保消息列表满足 LLM API 约束：role 为 tool 的消息必须紧接在带 tool_calls 的 assistant 消息之后。

    移除孤立的 tool 消息（即前面没有 assistant+tool_calls 的 tool 消息），
    避免 InternalError.Algo.InvalidParameter。
    """
    result: list[langchain_messages.BaseMessage] = []
    last_assistant_had_tool_calls = False

    for msg in messages:
        msg_type = getattr(msg, "type", None)
        if msg_type == "human" or isinstance(msg, langchain_messages.HumanMessage):
            last_assistant_had_tool_calls = False
            result.append(msg)
        elif msg_type == "system" or isinstance(msg, langchain_messages.SystemMessage):
            last_assistant_had_tool_calls = False
            result.append(msg)
        elif msg_type == "ai" or isinstance(msg, (langchain_messages.AIMessage, langchain_messages.AIMessageChunk)):
            tool_calls = getattr(msg, "tool_calls", None)
            last_assistant_had_tool_calls = bool(tool_calls and len(tool_calls) > 0)
            result.append(msg)
        elif msg_type == "tool" or isinstance(msg, langchain_messages.ToolMessage):
            if last_assistant_had_tool_calls:
                result.append(msg)
            # 否则跳过孤立的 tool 消息
        else:
            result.append(msg)

    return result
