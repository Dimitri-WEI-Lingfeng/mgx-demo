"""messages_to_langchain 单元测试。"""

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from shared.schemas import Message
from agents.utils.messages import messages_to_langchain
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage


def _make_msg_dict(role: str, content, **kwargs) -> dict:
    """构造 Message 的 model_dump 格式。"""
    base = {
        "message_id": "msg-test-001",
        "session_id": "sess-1",
        "role": role,
        "content": content,
        "timestamp": time.time(),
        "tool_calls": None,
        "tool_call_id": None,
        "parent_id": None,
        "agent_name": None,
        "cause_by": None,
        "sent_from": None,
        "send_to": [],
        "trace_id": None,
        "metadata": {},
    }
    base.update(kwargs)
    return base


class TestMessagesToLangchain:
    """测试 messages_to_langchain 转换。"""

    def test_messages_to_langchain_user(self):
        """user 消息正确转为 HumanMessage。"""
        msg = Message(**_make_msg_dict("user", "你好", message_id="m1"))
        result = messages_to_langchain([msg])
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)
        assert result[0].content == "你好"
        assert result[0].id == "m1"

    def test_messages_to_langchain_assistant_plain(self):
        """assistant 纯文本正确转为 AIMessage。"""
        msg = Message(**_make_msg_dict("assistant", "回复内容", message_id="m2"))
        result = messages_to_langchain([msg])
        assert len(result) == 1
        assert isinstance(result[0], AIMessage)
        assert result[0].content == "回复内容"
        assert result[0].id == "m2"
        assert result[0].tool_calls == []

    def test_messages_to_langchain_assistant_with_tool_calls(self):
        """assistant 含 tool_calls 正确转换，args=None 转为 {}。"""
        msg = Message(
            **_make_msg_dict(
                "assistant",
                "",
                message_id="m3",
                tool_calls=[
                    {"type": "tool_call", "id": "tc1", "name": "list_files", "args": {"dir": "."}},
                    {"type": "tool_call", "id": "tc2", "name": "read_file", "args": None},
                ],
            )
        )
        result = messages_to_langchain([msg])
        assert len(result) == 1
        assert isinstance(result[0], AIMessage)
        assert len(result[0].tool_calls) == 2
        assert result[0].tool_calls[0]["args"] == {"dir": "."}
        assert result[0].tool_calls[1]["args"] == {}
        assert result[0].id == "m3"

    def test_messages_to_langchain_system(self):
        """system 消息正确转为 SystemMessage。"""
        msg = Message(**_make_msg_dict("system", "You are helpful.", message_id="m4"))
        result = messages_to_langchain([msg])
        assert len(result) == 1
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == "You are helpful."
        assert result[0].id == "m4"

    def test_messages_to_langchain_tool(self):
        """tool 消息含 tool_call_id 正确转为 ToolMessage。"""
        msg = Message(**_make_msg_dict("tool", "file1.py, file2.py", message_id="m5", tool_call_id="tc1"))
        result = messages_to_langchain([msg])
        assert len(result) == 1
        assert isinstance(result[0], ToolMessage)
        assert result[0].content == "file1.py, file2.py"
        assert result[0].tool_call_id == "tc1"
        assert result[0].id == "m5"

    def test_messages_to_langchain_content_list(self):
        """content 为 list 的多模态正确传递。"""
        content_list = [{"type": "text", "text": "第一部分"}, {"type": "text", "text": "第二部分"}]
        msg = Message(**_make_msg_dict("user", content_list, message_id="m6"))
        result = messages_to_langchain([msg])
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)
        # ContentPart 转 dict 后可能含额外字段，核心是 type 和 text 正确
        content = result[0].content
        assert isinstance(content, list) and len(content) == 2
        assert content[0].get("text") == "第一部分" and content[1].get("text") == "第二部分"
        assert result[0].id == "m6"

    def test_messages_to_langchain_roundtrip(self):
        """Message -> dict -> Message -> LangChain 往返一致性。"""
        orig = [
            Message(**_make_msg_dict("user", "hi", message_id="u1")),
            Message(**_make_msg_dict("assistant", "hello", message_id="a1")),
            Message(
                **_make_msg_dict(
                    "assistant",
                    "",
                    message_id="a2",
                    tool_calls=[
                        {"type": "tool_call", "id": "tc1", "name": "x", "args": {"a": 1}},
                        {"type": "tool_call", "id": "tc2", "name": "y", "args": None},
                    ],
                )
            ),
            Message(**_make_msg_dict("tool", "result", message_id="t1", tool_call_id="tc1")),
        ]
        # 模拟 DB 往返
        reloaded = [Message(**m.model_dump()) for m in orig]
        lc = messages_to_langchain(reloaded)
        assert len(lc) == 4
        assert lc[0].content == "hi" and lc[0].id == "u1"
        assert lc[1].content == "hello" and lc[1].id == "a1"
        assert len(lc[2].tool_calls) == 2
        assert lc[2].tool_calls[0]["args"] == {"a": 1}
        assert lc[2].tool_calls[1]["args"] == {}
        assert lc[3].content == "result" and lc[3].tool_call_id == "tc1" and lc[3].id == "t1"
