"""实验 04：验证将 create_agent 作为 subgraph 节点时，astream 是否流出 ToolMessage。

当 subgraph 直接作为节点（add_node("agent", sub_agent)）时，subgraphs=True 应能捕获
子图内部的 ToolMessage 和 AIMessage(tool_calls)。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_community.chat_models.fake import FakeMessagesListChatModel
from langchain.tools import tool
from langgraph.graph import StateGraph, START, END


def _make_tool_call_msg(tool_name: str, args: dict, call_id: str = "call_fake"):
    """构造带 tool_calls 的 AIMessage。"""
    return AIMessage(
        content="",
        tool_calls=[{"id": call_id, "name": tool_name, "args": args, "type": "tool_call"}],
    )


def _create_fake_messages_llm_with_tools(responses: list):
    """创建支持 bind_tools 的 FakeMessagesListChatModel。"""
    from langchain_community.chat_models.fake import FakeMessagesListChatModel

    class FakeMessagesListChatModelWithTools(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    return FakeMessagesListChatModelWithTools(responses=list(responses))


@tool
def dummy_tool(x: str) -> str:
    """A dummy tool for testing."""
    return f"result: {x}"


def create_sub_agent_with_tools():
    """创建带 tool 的 agent 图（模拟 create_agent 返回的图）。"""
    # 响应序列：先返回 tool_call，再返回最终文本
    responses = [
        _make_tool_call_msg("dummy_tool", {"x": "test"}, "call_1"),
        AIMessage(content="工具调用完成，任务已完成。"),
    ]
    llm = _create_fake_messages_llm_with_tools(responses)
    from langchain.agents import create_agent

    agent = create_agent(
        model=llm,
        tools=[dummy_tool],
        system_prompt="You are a helpful assistant. Use tools when needed.",
    )
    return agent


def create_parent_graph_with_subgraph_as_node():
    """父图：将 sub_agent 直接作为节点（非包装函数）。"""
    sub_agent = create_sub_agent_with_tools()

    class ParentState(dict):
        messages: list

    # 子 agent 作为节点直接加入
    workflow = StateGraph(ParentState)
    workflow.add_node("agent", sub_agent)
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", END)
    return workflow.compile()


def create_parent_graph_with_wrapper():
    """父图：使用包装函数 + ainvoke（当前 team graph 结构）。"""
    sub_agent = create_sub_agent_with_tools()

    class ParentState(dict):
        messages: list

    async def agent_node(state):
        result = await sub_agent.ainvoke({"messages": state["messages"]})
        output = result.get("messages", [])
        last = output[-1].content if output else ""
        return {"messages": [AIMessage(content=f"[Agent] {last}")]}

    workflow = StateGraph(ParentState)
    workflow.add_node("agent", agent_node)
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", END)
    return workflow.compile()


async def run_experiment(name: str, graph, initial_state: dict):
    """运行实验并统计消息类型。"""
    print(f"\n--- {name} ---")
    msg_types = {}
    tool_messages = 0
    ai_with_tool_calls = 0

    async for stream_output in graph.astream(
        initial_state,
        stream_mode=["updates", "messages"],
        subgraphs=True,
    ):
        if len(stream_output) != 3:
            continue
        namespace, stream_mode, chunk = stream_output
        if stream_mode != "messages":
            continue
        if not isinstance(chunk, tuple) or len(chunk) != 2:
            continue
        msg, meta = chunk
        t = type(msg).__name__
        msg_types[t] = msg_types.get(t, 0) + 1
        if t == "ToolMessage":
            tool_messages += 1
        elif t == "AIMessage" and getattr(msg, "tool_calls", None):
            ai_with_tool_calls += 1

    print(f"  消息类型统计: {msg_types}")
    print(f"  ToolMessage 数量: {tool_messages}")
    print(f"  AIMessage(tool_calls) 数量: {ai_with_tool_calls}")


async def main():
    print("=" * 60)
    print("实验 04: subgraph 作为节点时 astream 是否流出 ToolMessage")
    print("=" * 60)

    initial_state = {"messages": [HumanMessage(content="请帮我测试")]}

    # 结构 A：subgraph 直接作为节点
    graph_a = create_parent_graph_with_subgraph_as_node()
    await run_experiment(
        "结构 A: add_node('agent', sub_agent) 直接作为节点",
        graph_a,
        initial_state,
    )

    # 结构 B：包装函数 + ainvoke（当前 team graph 结构）
    graph_b = create_parent_graph_with_wrapper()
    await run_experiment(
        "结构 B: 包装函数 + ainvoke（当前 team graph 结构）",
        graph_b,
        initial_state,
    )

    print("\n结论: 两种结构均可在 stream 中得到 ToolMessage（取决于 create_agent 内部实现）。")
    print("  关键：图节点需返回或透传子 agent 的完整 messages，而非仅取 content 包装。")


if __name__ == "__main__":
    asyncio.run(main())
