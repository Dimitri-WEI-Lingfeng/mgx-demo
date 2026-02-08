"""实验 03：模拟 run_agent 的 event 发送逻辑，记录 updates/messages 与 node_start/llm_stream/message_complete 的时序。

复现 run_agent 的 astream 循环逻辑，但不写入 DB，仅打印将发送的事件序列。
"""

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import langchain_core.messages as langchain_messages
from research_langgraph.experiment_01_astream_format import create_minimal_graph
from langchain_core.messages import HumanMessage


def _get_message_id(msg) -> str:
    return getattr(msg, "message_id", None) or getattr(msg, "id", None) or str(uuid.uuid4())


async def main():
    print("=" * 60)
    print("实验 03: run_agent 事件发送时序模拟")
    print("=" * 60)

    graph = create_minimal_graph()
    initial_state = {"messages": [HumanMessage(content="做一个待办应用")]}

    # 模拟 run_agent 的变量
    last_node = None
    current_node = None
    llm_streaming = False
    current_message_content = ""
    current_message_node = None
    current_streaming_message_id = None
    current_parent_message_id = "user-msg-id"
    events_log = []

    async for stream_output in graph.astream(
        initial_state,
        stream_mode=["updates", "messages"],
        subgraphs=True,
    ):
        namespace, stream_mode, chunk = stream_output

        # 当 namespace 为空时，run_agent 会走特殊分支（只处理 messages，不发送 node_start/llm_stream）
        # 本实验模拟「若按 metadata 的 node 处理」时的事件顺序
        if not namespace:
            if stream_mode == "updates":
                # updates 且 namespace=()：run_agent 会 continue 跳过
                events_log.append(("SKIP", "updates", "namespace=() 时 run_agent 跳过 updates"))
                continue
            if not isinstance(chunk, tuple) or len(chunk) != 2:
                continue
            message, metadata = chunk
            node_name = metadata.get("langgraph_node", "?")
            # 模拟：按 messages 处理，用 metadata 的 node 作为 current_node
            current_node = node_name
            stream_mode = "messages"
            # 不 continue，fall through 到下面的 messages 处理
        else:
            current_node = namespace[0].split(":")[0]

        if stream_mode == "updates":
            node_output = chunk
            if llm_streaming:
                llm_streaming = False

            if current_node != last_node:
                if last_node:
                    if current_message_content and current_message_node:
                        events_log.append(
                            ("MESSAGE_COMPLETE", last_node, f"content_len={len(current_message_content)}")
                        )
                        events_log.append(("NODE_END", last_node, ""))
                    current_message_content = ""
                    current_message_node = None
                    current_streaming_message_id = None

                events_log.append(("NODE_START", current_node, ""))
                last_node = current_node

        elif stream_mode == "messages":
            if not isinstance(chunk, tuple) or len(chunk) != 2:
                continue
            message_chunk, metadata = chunk
            node_name = metadata.get("langgraph_node", current_node or "unknown")

            if isinstance(message_chunk, langchain_messages.AIMessageChunk):
                if not llm_streaming:
                    llm_streaming = True
                    current_streaming_message_id = message_chunk.id or str(uuid.uuid4())
                    current_message_content = ""
                    current_message_node = node_name
                    events_log.append(("LLM_STREAM_START", node_name, f"msg_id={current_streaming_message_id[:30]}..."))

                chunk_text = message_chunk.text if message_chunk.content else ""
                if chunk_text:
                    current_message_content += chunk_text
                    events_log.append(("LLM_STREAM", node_name, f"delta={repr(chunk_text)[:20]}"))

    # 循环结束后，保存最后一条消息
    if current_message_content and current_message_node:
        events_log.append(("MESSAGE_COMPLETE", current_message_node, f"content_len={len(current_message_content)}"))
    if last_node:
        events_log.append(("NODE_END", last_node, ""))

    print("\n事件序列（按发生顺序）:")
    for i, (evt, node, detail) in enumerate(events_log):
        print(f"  {i+1:3}. {evt:20} node={node or '-':15} {detail}")

    print(f"\n总事件数: {len(events_log)}")
    print("\n注意: 当 namespace=() 时，run_agent 不会进入 updates/messages 主分支，")
    print("      所有 chunk 走 'if not namespace' 分支，本实验仅模拟 namespace 非空时的逻辑。")


if __name__ == "__main__":
    asyncio.run(main())
