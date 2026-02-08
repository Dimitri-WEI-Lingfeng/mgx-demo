"""实验 06：验证 MESSAGE_COMPLETE 事件应包含的完整 data 字段。

不依赖真实 graph，直接构造 create_event 调用应传入的 data 结构。
前端 sse.ts 期望: content, role, tool_calls, tool_call_id。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def _normalize_tool_calls(tool_calls) -> list[dict]:
    """Convert LangChain tool_calls to Message schema format (from run_agent)."""
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


def build_message_complete_data_for_ai_message(content: str, tool_calls: list | None):
    """AIMessage 的 MESSAGE_COMPLETE 应包含的 data。"""
    return {
        "content": content,
        "role": "assistant",
        "tool_calls": _normalize_tool_calls(tool_calls or []),
    }


def build_message_complete_data_for_tool_message(content: str, tool_call_id: str | None):
    """ToolMessage 的 MESSAGE_COMPLETE 应包含的 data。"""
    return {
        "content": content,
        "role": "tool",
        "tool_call_id": tool_call_id,
    }


def main():
    print("=" * 60)
    print("实验 06: MESSAGE_COMPLETE 事件应包含的完整 data 字段")
    print("=" * 60)

    # AIMessage 示例
    ai_data = build_message_complete_data_for_ai_message(
        content="让我调用工具",
        tool_calls=[
            {"id": "call_1", "name": "list_files", "args": {"directory": "."}, "type": "tool_call"},
        ],
    )
    print("\nAIMessage 的 MESSAGE_COMPLETE data:")
    print("  ", ai_data)
    assert "content" in ai_data
    assert "role" in ai_data
    assert "tool_calls" in ai_data
    assert len(ai_data["tool_calls"]) == 1
    assert ai_data["tool_calls"][0]["name"] == "list_files"

    # ToolMessage 示例
    tool_data = build_message_complete_data_for_tool_message(
        content="file1.py, file2.py",
        tool_call_id="call_1",
    )
    print("\nToolMessage 的 MESSAGE_COMPLETE data:")
    print("  ", tool_data)
    assert "content" in tool_data
    assert "role" in tool_data
    assert "tool_call_id" in tool_data
    assert tool_data["tool_call_id"] == "call_1"

    # AIMessage 无 tool_calls 示例
    ai_simple = build_message_complete_data_for_ai_message("简单回复", None)
    print("\nAIMessage 无 tool_calls 的 data:")
    print("  ", ai_simple)
    assert ai_simple["tool_calls"] == []

    print("\n结论: 前端 sse.ts 需 data.content, data.role, data.tool_calls, data.tool_call_id 才能正确更新消息。")


if __name__ == "__main__":
    main()
