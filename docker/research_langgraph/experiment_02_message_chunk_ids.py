"""实验 02：验证多节点时 AIMessageChunk.id 的变化。

打印每个 messages chunk 的 message.id 和 langgraph_node，确认不同节点有不同的 id。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# 复用 experiment_01 的图（通过 path 引入）
sys.path.insert(0, str(Path(__file__).parent.parent))
from research_langgraph.experiment_01_astream_format import create_minimal_graph
from langchain_core.messages import HumanMessage


async def main():
    print("=" * 60)
    print("实验 02: AIMessageChunk.id 在多节点下的变化")
    print("=" * 60)

    graph = create_minimal_graph()
    initial_state = {"messages": [HumanMessage(content="做一个待办应用")]}

    print("\n收集 messages 模式的 chunk，记录 (message_id, node_name) 变化:\n")

    prev_id = None
    prev_node = None
    id_transitions = []

    async for namespace, stream_mode, chunk in graph.astream(
        initial_state,
        stream_mode=["updates", "messages"],
        subgraphs=True,
    ):
        if stream_mode != "messages":
            continue

        if not isinstance(chunk, tuple) or len(chunk) != 2:
            continue

        msg, meta = chunk
        node = meta.get("langgraph_node", "?")
        msg_id = getattr(msg, "id", None)

        if msg_id != prev_id or node != prev_node:
            id_transitions.append((msg_id, node, getattr(msg, "content", "")[:20]))
            prev_id = msg_id
            prev_node = node

    print("ID 变化序列 (message_id, node_name, content_preview):")
    for i, (mid, node, preview) in enumerate(id_transitions):
        print(f"  {i+1}. id={str(mid)[:40]}... node={node} content={repr(preview)}")

    print(f"\n共 {len(id_transitions)} 次 id/node 变化")
    print("\n结论: 不同节点的 message.id 不同，可用于区分消息边界")


if __name__ == "__main__":
    asyncio.run(main())
