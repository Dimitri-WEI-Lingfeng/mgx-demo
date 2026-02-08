"""测试 LangChain 是否在不同线程中执行工具调用。"""

import threading
from langchain.tools import tool
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# 记录线程 ID
main_thread_id = threading.get_ident()
tool_thread_ids = []


@tool
def test_tool(input: str) -> str:
    """一个简单的测试工具。"""
    thread_id = threading.get_ident()
    tool_thread_ids.append(thread_id)
    print(f"Tool 执行线程 ID: {thread_id}")
    print(f"主线程 ID: {main_thread_id}")
    print(f"是否在同一线程: {thread_id == main_thread_id}")
    return f"工具执行完成，线程 ID: {thread_id}"


def main():
    print(f"主线程 ID: {main_thread_id}\n")
    
    llm = ChatOpenAI(model="qwen3-coder-flash")
    
    agent = create_agent(
        model=llm,
        tools=[test_tool],
        system_prompt="你是一个助手，可以调用工具。"
    )
    
    print("调用 agent...\n")
    result = agent.invoke({
        "messages": [HumanMessage(content="请调用 test_tool 工具")]
    })
    
    print("\n结果:")
    print(f"主线程 ID: {main_thread_id}")
    print(f"工具执行线程 IDs: {tool_thread_ids}")
    print(f"是否在同一线程: {all(tid == main_thread_id for tid in tool_thread_ids)}")


if __name__ == '__main__':
    main()
