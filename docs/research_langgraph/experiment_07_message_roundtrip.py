"""实验 07：验证 Message 与 LangChain 格式的双向转换及往返一致性。

构造各类 Message（user/assistant/system/tool，含 tool_calls、list content），
模拟 model_dump() -> Message(**dict) 的 DB 往返，
转为 LangChain 后再提取回可比较结构，记录哪些场景会丢失或格式不一致。
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from shared.schemas import Message


def _current_conversion_to_langchain(msg: Message):
    """复制 run_agent.py 中修复前的转换逻辑（用于对比）。"""
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

    if msg.role == "user":
        return HumanMessage(content=msg.content)
    elif msg.role == "assistant":
        tool_calls = (
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
        )
        return AIMessage(content=msg.content, tool_calls=tool_calls)
    elif msg.role == "system":
        return SystemMessage(content=msg.content)
    elif msg.role == "tool":
        return ToolMessage(content=msg.content, tool_call_id=msg.tool_call_id)
    return None


def _extract_from_langchain(lc_msg) -> dict:
    """从 LangChain 消息提取可比较的字段。"""
    role = getattr(lc_msg, "type", "unknown")
    if role == "human":
        role = "user"
    content = getattr(lc_msg, "content", "")
    tool_calls = getattr(lc_msg, "tool_calls", None) or []
    tool_call_id = getattr(lc_msg, "tool_call_id", None)
    msg_id = getattr(lc_msg, "id", None)
    return {
        "role": role,
        "content": content,
        "tool_calls": tool_calls,
        "tool_call_id": tool_call_id,
        "message_id": msg_id,
    }


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


def main():
    print("=" * 60)
    print("实验 07: Message 与 LangChain 往返一致性")
    print("=" * 60)

    issues = []
    ok_count = 0

    # 1. User 消息（纯文本）
    print("\n--- 1. User 消息（纯文本） ---")
    msg = Message(**_make_msg_dict("user", "你好"))
    dumped = msg.model_dump()
    reloaded = Message(**dumped)
    lc = _current_conversion_to_langchain(reloaded)
    extracted = _extract_from_langchain(lc)
    if extracted["content"] == msg.content and extracted["role"] == "user":
        print("  OK: content 和 role 一致")
        ok_count += 1
    else:
        issues.append(f"User 纯文本: content={extracted['content']!r} vs {msg.content!r}")
    if extracted["message_id"] is None:
        issues.append("User: message_id 未保留")

    # 2. Assistant 纯文本
    print("\n--- 2. Assistant 纯文本 ---")
    msg = Message(**_make_msg_dict("assistant", "回复内容"))
    reloaded = Message(**msg.model_dump())
    lc = _current_conversion_to_langchain(reloaded)
    extracted = _extract_from_langchain(lc)
    if extracted["content"] == msg.content:
        print("  OK: content 一致")
        ok_count += 1
    else:
        issues.append(f"Assistant 纯文本: content 不一致")
    if extracted["message_id"] is None:
        issues.append("Assistant: message_id 未保留")

    # 3. Assistant + tool_calls（含 args=None）
    print("\n--- 3. Assistant + tool_calls（含 args=None） ---")
    tool_calls = [
        {"type": "tool_call", "id": "tc1", "name": "list_files", "args": {"directory": "."}},
        {"type": "tool_call", "id": "tc2", "name": "read_file", "args": None},
    ]
    msg = Message(**_make_msg_dict("assistant", "", tool_calls=tool_calls))
    reloaded = Message(**msg.model_dump())
    try:
        lc = _current_conversion_to_langchain(reloaded)
        extracted = _extract_from_langchain(lc)
        tc_args = [tc.get("args") for tc in extracted["tool_calls"]]
        if tc_args[1] is None:
            issues.append("Assistant tool_calls: args=None 未转为 {}，可能导致 LangChain/API 报错")
        else:
            print("  OK: tool_calls 格式正确")
            ok_count += 1
        if len(extracted["tool_calls"]) != 2:
            issues.append(f"Assistant tool_calls: 数量 {len(extracted['tool_calls'])} != 2")
    except Exception as e:
        issues.append(f"Assistant tool_calls: 转换失败 - {e} (args=None 导致 LangChain ValidationError)")

    # 4. System 消息
    print("\n--- 4. System 消息 ---")
    msg = Message(**_make_msg_dict("system", "You are helpful."))
    reloaded = Message(**msg.model_dump())
    lc = _current_conversion_to_langchain(reloaded)
    extracted = _extract_from_langchain(lc)
    if extracted["content"] == msg.content:
        print("  OK: content 一致")
        ok_count += 1
    else:
        issues.append("System: content 不一致")
    if extracted["message_id"] is None:
        issues.append("System: message_id 未保留")

    # 5. Tool 消息 + tool_call_id
    print("\n--- 5. Tool 消息 + tool_call_id ---")
    msg = Message(**_make_msg_dict("tool", "file1.py, file2.py", tool_call_id="tc1"))
    reloaded = Message(**msg.model_dump())
    lc = _current_conversion_to_langchain(reloaded)
    extracted = _extract_from_langchain(lc)
    if extracted["content"] == msg.content and extracted["tool_call_id"] == "tc1":
        print("  OK: content 和 tool_call_id 一致")
        ok_count += 1
    else:
        issues.append(f"Tool: content={extracted['content']!r} tool_call_id={extracted['tool_call_id']!r}")
    if extracted["message_id"] is None:
        issues.append("Tool: message_id 未保留")

    # 6. content 为 list（多模态，纯 dict）
    print("\n--- 6. content 为 list（多模态，纯 dict） ---")
    content_list = [
        {"type": "text", "text": "第一部分"},
        {"type": "text", "text": "第二部分"},
    ]
    msg = Message(**_make_msg_dict("user", content_list))
    try:
        dumped = msg.model_dump()
        reloaded = Message(**dumped)
        lc = _current_conversion_to_langchain(reloaded)
        extracted = _extract_from_langchain(lc)
        if isinstance(extracted["content"], list) and len(extracted["content"]) == 2:
            texts = [
                p.get("text", "") or ""
                for p in extracted["content"]
                if isinstance(p, dict) and p.get("type") == "text"
            ]
            if "".join(texts) == "第一部分第二部分":
                print("  OK: list content 正确传递")
                ok_count += 1
            else:
                issues.append(f"content list: 文本提取后={texts!r}")
        else:
            issues.append(f"content list: 结构变化 {type(extracted['content'])} {extracted['content']!r}")
    except Exception as e:
        issues.append(f"content list: 转换异常 {e}")

    # 7. 模拟 DB 往返（ContentPart 反序列化后为 Pydantic 对象）
    print("\n--- 7. DB 往返后 ContentPart 反序列化 ---")
    content_parts = [
        {"type": "text", "text": "Hello"},
        {"type": "text", "text": "World"},
    ]
    msg = Message(**_make_msg_dict("assistant", content_parts))
    dumped = msg.model_dump()
    reloaded = Message(**dumped)
    try:
        lc = _current_conversion_to_langchain(reloaded)
        extracted = _extract_from_langchain(lc)
        if isinstance(extracted["content"], list):
            texts = [p.get("text", "") for p in extracted["content"] if isinstance(p, dict)]
            combined = " ".join(texts) if texts else str(extracted["content"])
        else:
            combined = extracted["content"]
        if "Hello" in str(combined) and "World" in str(combined):
            print("  OK: DB 往返后 list content 可读")
            ok_count += 1
        else:
            issues.append(f"DB 往返 content: {extracted['content']!r}")
    except Exception as e:
        issues.append(
            f"DB 往返 content: 转换异常 - {e} "
            "(ContentPart 对象需转为 dict 才能传给 LangChain)"
        )

    # 汇总（修复前）
    print("\n" + "=" * 60)
    print("【修复前】")
    print(f"通过: {ok_count}/7")
    if issues:
        print("发现的问题:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("未发现明显问题")

    # 使用修复后的 messages_to_langchain 验证
    print("\n" + "=" * 60)
    print("【修复后 - messages_to_langchain】")
    from agents.utils import messages_to_langchain

    test_messages = [
        Message(**_make_msg_dict("user", "你好", message_id="m1")),
        Message(**_make_msg_dict("assistant", "回复", message_id="m2")),
        Message(**_make_msg_dict("assistant", "", message_id="m3", tool_calls=[
            {"type": "tool_call", "id": "tc1", "name": "list_files", "args": {"dir": "."}},
            {"type": "tool_call", "id": "tc2", "name": "read_file", "args": None},
        ])),
        Message(**_make_msg_dict("system", "You are helpful.", message_id="m4")),
        Message(**_make_msg_dict("tool", "result", message_id="m5", tool_call_id="tc1")),
        Message(**_make_msg_dict("user", [{"type": "text", "text": "多模态"}], message_id="m6")),
    ]
    try:
        lc_msgs = messages_to_langchain(test_messages)
        assert len(lc_msgs) == 6
        for i, lc in enumerate(lc_msgs):
            assert getattr(lc, "id", None) == test_messages[i].message_id
        print("  OK: 所有场景均可正确转换，含 tool_calls args=None、list content、message_id")
    except Exception as e:
        print(f"  失败: {e}")

    print("=" * 60)


if __name__ == "__main__":
    main()
