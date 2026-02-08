"""ensure_messages 单测。"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.utils.messages import ensure_messages


class TestEnsureMessages:
    """测试 ensure_messages：确保 tool 消息紧接在带 tool_calls 的 assistant 之后。"""

    def test_empty_list_returns_empty(self):
        """空列表返回空列表。"""
        assert ensure_messages([]) == []

    def test_no_tool_messages_passthrough(self):
        """无 tool 消息时，原样返回。"""
        msgs = [
            HumanMessage(content="hi"),
            AIMessage(content="hello"),
        ]
        result = ensure_messages(msgs)
        assert len(result) == 2
        assert result[0].content == "hi"
        assert result[1].content == "hello"

    def test_valid_tool_after_assistant_with_tool_calls_kept(self):
        """assistant 带 tool_calls 后的 tool 消息保留。"""
        msgs = [
            HumanMessage(content="查天气"),
            AIMessage(
                content="",
                tool_calls=[{"id": "c1", "name": "get_weather", "args": {"city": "北京"}}],
            ),
            ToolMessage(content="晴", tool_call_id="c1"),
        ]
        result = ensure_messages(msgs)
        assert len(result) == 3
        assert result[2].content == "晴"

    def test_orphan_tool_at_start_removed(self):
        """开头的孤立 tool 消息被移除。"""
        msgs = [
            ToolMessage(content="orphan", tool_call_id="c1"),
            HumanMessage(content="hi"),
        ]
        result = ensure_messages(msgs)
        assert len(result) == 1
        assert result[0].content == "hi"

    def test_orphan_tool_after_user_removed(self):
        """user 消息后的孤立 tool 消息被移除。"""
        msgs = [
            HumanMessage(content="hi"),
            ToolMessage(content="orphan", tool_call_id="c1"),
        ]
        result = ensure_messages(msgs)
        assert len(result) == 1
        assert result[0].content == "hi"

    def test_orphan_tool_after_assistant_without_tool_calls_removed(self):
        """assistant 无 tool_calls 后的 tool 消息被移除。"""
        msgs = [
            HumanMessage(content="hi"),
            AIMessage(content="hello"),  # 无 tool_calls
            ToolMessage(content="orphan", tool_call_id="c1"),
        ]
        result = ensure_messages(msgs)
        assert len(result) == 2
        assert result[0].content == "hi"
        assert result[1].content == "hello"

    def test_orphan_tool_after_assistant_with_empty_tool_calls_removed(self):
        """assistant 的 tool_calls 为空时，其后的 tool 消息被移除。"""
        msgs = [
            AIMessage(content="ok", tool_calls=[]),
            ToolMessage(content="orphan", tool_call_id="c1"),
        ]
        result = ensure_messages(msgs)
        assert len(result) == 1
        assert result[0].content == "ok"

    def test_multiple_tool_messages_after_one_assistant_all_kept(self):
        """一个 assistant 后的多条 tool 消息全部保留。"""
        msgs = [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "c1", "name": "a", "args": {}},
                    {"id": "c2", "name": "b", "args": {}},
                ],
            ),
            ToolMessage(content="r1", tool_call_id="c1"),
            ToolMessage(content="r2", tool_call_id="c2"),
        ]
        result = ensure_messages(msgs)
        assert len(result) == 3
        assert result[1].content == "r1"
        assert result[2].content == "r2"

    def test_mixed_removes_only_orphan_tool(self):
        """混合场景：仅移除孤立的 tool 消息。"""
        msgs = [
            HumanMessage(content="hi"),
            AIMessage(content="", tool_calls=[{"id": "c1", "name": "x", "args": {}}]),
            ToolMessage(content="r1", tool_call_id="c1"),
            AIMessage(content="ok"),  # 无 tool_calls
            ToolMessage(content="orphan", tool_call_id="c2"),
        ]
        result = ensure_messages(msgs)
        assert len(result) == 4
        assert result[0].content == "hi"
        assert result[1].content == ""
        assert result[2].content == "r1"
        assert result[3].content == "ok"
        # orphan 的 tool 消息已移除

    def test_system_message_resets_state(self):
        """system 消息会重置状态，其后的 tool 为孤立。"""
        msgs = [
            AIMessage(content="", tool_calls=[{"id": "c1", "name": "x", "args": {}}]),
            ToolMessage(content="r1", tool_call_id="c1"),
            SystemMessage(content="you are helpful"),
            ToolMessage(content="orphan", tool_call_id="c2"),
        ]
        result = ensure_messages(msgs)
        assert len(result) == 3
        assert result[2].content == "you are helpful"

    def test_human_message_resets_state(self):
        """human 消息会重置状态。"""
        msgs = [
            AIMessage(content="", tool_calls=[{"id": "c1", "name": "x", "args": {}}]),
            ToolMessage(content="r1", tool_call_id="c1"),
            HumanMessage(content="next"),
            ToolMessage(content="orphan", tool_call_id="c2"),
        ]
        result = ensure_messages(msgs)
        assert len(result) == 3
        assert result[2].content == "next"

    def test_ai_with_tool_calls_without_responses_stripped(self):
        """AIMessage 含 tool_calls 但无 ToolMessage 响应时，去掉 tool_calls 避免 API 报错。"""
        msgs = [
            HumanMessage(content="hi"),
            AIMessage(
                content="调用工具",
                tool_calls=[{"id": "c1", "name": "get_weather", "args": {}}],
            ),
            HumanMessage(content="继续"),
        ]
        result = ensure_messages(msgs)
        assert len(result) == 3
        assert getattr(result[1], "tool_calls", None) == []
        assert result[1].content == "调用工具"

    def test_ai_with_tool_calls_incomplete_responses_stripped(self):
        """AIMessage 含多个 tool_calls，但只有部分 ToolMessage 响应时，去掉 tool_calls。"""
        msgs = [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "c1", "name": "a", "args": {}},
                    {"id": "c2", "name": "b", "args": {}},
                ],
            ),
            ToolMessage(content="r1", tool_call_id="c1"),
            HumanMessage(content="next"),
        ]
        result = ensure_messages(msgs)
        assert len(result) == 2
        assert getattr(result[0], "tool_calls", None) == []
