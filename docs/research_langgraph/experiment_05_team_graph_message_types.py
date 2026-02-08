"""实验 05：验证当前 team graph 的 astream 实际产出哪些消息类型。

使用与实际 team graph 相同的结构（wrapper 函数 + ainvoke），记录 stream 中所有 message 类型。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.chat_models.fake import FakeListChatModel
from langchain.tools import tool
from langgraph.graph import StateGraph, START, END


@tool
def simple_tool(x: str) -> str:
    """A simple tool."""
    return f"result: {x}"


def _create_fake_llm_with_tools(responses: list):
    """创建支持 bind_tools 的 FakeListChatModel。"""
    class FakeWithTools(FakeListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    return FakeWithTools(responses=responses.copy())


def create_agent_with_tools():
    """创建带 tool 的 agent（模拟 boss_agent）。"""
    from langchain.agents import create_agent

    llm = _create_fake_llm_with_tools(["已调用工具", "任务完成"])
    agent = create_agent(
        model=llm,
        tools=[simple_tool],
        system_prompt="You are helpful.",
    )
    return agent


def create_team_graph_like_structure():
    """创建与 team graph 相同结构的图：wrapper 函数 + ainvoke。"""
    agent = create_agent_with_tools()

    class State(dict):
        messages: list
        next_agent: str

    async def boss_node(state):
        messages = list(state["messages"]) + [HumanMessage(content="请执行任务")]
        result = await agent.ainvoke({"messages": messages})
        output_messages = result.get("messages", [])
        output = output_messages[-1].content if output_messages else ""
        return {
            "messages": [AIMessage(content=f"[Boss] {output}")],
            "next_agent": "end",
        }

    workflow = StateGraph(State)
    workflow.add_node("boss", boss_node)
    workflow.add_edge(START, "boss")
    workflow.add_edge("boss", END)
    return workflow.compile()


async def main():
    print("=" * 60)
    print("实验 05: 当前 team graph 结构的 astream 产出消息类型")
    print("=" * 60)

    graph = create_team_graph_like_structure()
    initial_state = {"messages": [HumanMessage(content="做一个待办应用")], "next_agent": None}

    msg_types = {}
    namespaces_seen = set()
    all_message_details = []

    print("\n调用 astream(stream_mode=['updates', 'messages'], subgraphs=True)\n")

    async for stream_output in graph.astream(
        initial_state,
        stream_mode=["updates", "messages"],
        subgraphs=True,
    ):
        if len(stream_output) != 3:
            continue
        namespace, stream_mode, chunk = stream_output

        if stream_mode == "messages" and isinstance(chunk, tuple) and len(chunk) == 2:
            msg, meta = chunk
            t = type(msg).__name__
            msg_types[t] = msg_types.get(t, 0) + 1
            ns = str(namespace)
            if ns not in namespaces_seen:
                namespaces_seen.add(ns)
            has_tool_calls = bool(getattr(msg, "tool_calls", None))
            all_message_details.append({
                "type": t,
                "namespace": ns,
                "has_tool_calls": has_tool_calls,
                "content_preview": str(getattr(msg, "content", ""))[:50],
            })

    print("消息类型统计:", msg_types)
    print("Namespace 集合:", namespaces_seen)
    print("\n前 10 条消息详情:")
    for i, d in enumerate(all_message_details[:10]):
        print(f"  {i+1}. {d['type']} namespace={d['namespace']} tool_calls={d['has_tool_calls']} content={d['content_preview']!r}")

    tool_msg_count = sum(1 for d in all_message_details if d["type"] == "ToolMessage")
    ai_tool_calls_count = sum(1 for d in all_message_details if d["type"] == "AIMessage" and d["has_tool_calls"])

    print(f"\n结论: ToolMessage={tool_msg_count}, AIMessage(tool_calls)={ai_tool_calls_count}")
    print("  当前结构下，stream 不包含 ToolMessage（子 agent 用 ainvoke 包装，不流出内部消息）。")

if __name__ == "__main__":
    asyncio.run(main())
