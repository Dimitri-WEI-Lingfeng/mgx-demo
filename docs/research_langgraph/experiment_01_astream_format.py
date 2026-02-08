"""实验 01：打印 LangGraph astream 的原始输出格式。

最小化 team graph（仅 boss + pm），打印每次 astream 迭代的 (namespace, stream_mode, chunk) 结构。
使用 FakeListChatModel 避免 API 调用。
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.chat_models.fake import FakeListChatModel
from langgraph.graph import StateGraph, END
from typing import Literal


def _create_fake_llm():
    """创建 FakeListChatModel，为 boss 和 pm 各提供简短响应。"""
    return FakeListChatModel(responses=[
        "[Boss] 需求分析完成，已创建 requirements.md",
        "[PM] PRD 文档已编写完成",
    ])


def create_minimal_graph():
    """创建最小团队图：仅 boss -> pm -> END。"""
    llm = _create_fake_llm()

    class State(dict):
        messages: list
        next_agent: str

    async def boss_node(state):
        last = state["messages"][-1]
        result = await llm.ainvoke([HumanMessage(content=f"分析需求: {last.content}")])
        return {
            "messages": [AIMessage(content=f"[Boss] {result.content}")],
            "next_agent": "product_manager",
        }

    async def pm_node(state):
        result = await llm.ainvoke([HumanMessage(content="请编写 PRD")])
        return {
            "messages": [AIMessage(content=f"[PM] {result.content}")],
            "next_agent": END,
        }

    def router(state):
        n = state.get("next_agent")
        if n == "product_manager":
            return "product_manager"
        return END

    workflow = StateGraph(dict)
    workflow.add_node("boss", boss_node)
    workflow.add_node("product_manager", pm_node)
    workflow.set_entry_point("boss")
    workflow.add_conditional_edges("boss", router, {"product_manager": "product_manager", END: END})
    workflow.add_edge("product_manager", END)
    return workflow.compile()


async def main():
    print("=" * 60)
    print("实验 01: LangGraph astream 输出格式")
    print("=" * 60)

    graph = create_minimal_graph()
    initial_state = {"messages": [HumanMessage(content="做一个待办应用")], "next_agent": "boss"}

    # 修正 initial_state：router 需要 next_agent，boss 节点会设置
    initial_state = {"messages": [HumanMessage(content="做一个待办应用")], "next_agent": None}

    # 需要符合 TeamState 结构，但我们的简化版用 dict
    # 直接运行看看
    initial_state = {"messages": [HumanMessage(content="做一个待办应用")]}

    print("\n调用 astream(stream_mode=['updates', 'messages'], subgraphs=True)\n")

    count = 0
    async for stream_output in graph.astream(
        initial_state,
        stream_mode=["updates", "messages"],
        subgraphs=True,
    ):
        count += 1
        print(f"--- Chunk #{count} ---")
        print(f"  type(stream_output): {type(stream_output)}")
        print(f"  len(stream_output): {len(stream_output)}")

        if len(stream_output) == 3:
            namespace, stream_mode, chunk = stream_output
            print(f"  namespace: {namespace} (type={type(namespace).__name__})")
            print(f"  stream_mode: {stream_mode}")
            print(f"  chunk type: {type(chunk).__name__}")

            if stream_mode == "updates":
                if isinstance(chunk, dict):
                    for k, v in chunk.items():
                        print(f"    updates[{k}]: {type(v).__name__} = {str(v)[:80]}...")
                else:
                    print(f"    chunk: {chunk}")
            elif stream_mode == "messages":
                if isinstance(chunk, tuple) and len(chunk) == 2:
                    msg, meta = chunk
                    print(f"    message type: {type(msg).__name__}")
                    print(f"    message.id: {getattr(msg, 'id', 'N/A')}")
                    print(f"    message.content (first 50): {str(getattr(msg, 'content', msg))[:50]}")
                    print(f"    metadata: {meta}")
                else:
                    print(f"    chunk: {chunk}")
        else:
            print(f"  raw: {stream_output}")

        print()

    print(f"\n总 chunk 数: {count}")


if __name__ == "__main__":
    asyncio.run(main())
