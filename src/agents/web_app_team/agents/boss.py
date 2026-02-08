"""Boss Agent - 需求提炼。"""

from collections.abc import Sequence

from agents.context import set_context
from agents.context.memory import InMemoryContext
from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentMiddleware
from langchain_openai import ChatOpenAI

from agents.web_app_team.tools.workspace_tools import read_file, write_file, list_files
from agents.web_app_team.tools.workflow_decision import workflow_decision
from agents.web_app_team.prompts.boss import BOSS_SYSTEM_PROMPT
from agents.cli_ui import stream_agent_with_ui


def create_boss_agent(
    llm: ChatOpenAI,
    callbacks: list = None,
    middleware: Sequence[AgentMiddleware] = (),
):
    """创建 Boss Agent。
    
    Args:
        llm: 语言模型
        callbacks: 回调函数列表
        middleware: 可选 middleware 列表（如 SummarizationMiddleware）
    
    Returns:
        Compiled agent graph
    
    Note:
        需要通过 context.set_context() 设置 AgentContext 后才能使用
    """
    tools = [
        read_file,
        write_file,
        list_files,
        workflow_decision,
    ]
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=BOSS_SYSTEM_PROMPT,
        middleware=list(middleware),
    )
    return agent



if __name__ == '__main__':

    from agents.context import set_context

    from langchain_core.messages import HumanMessage

    context = InMemoryContext(
            workspace_path='./workspace',
        )
    
    # 设置上下文
    set_context(context)


    llm = ChatOpenAI(model="qwen3-coder-flash")

    agent = create_boss_agent(llm)

    inputs = {"messages": [{"role": "user", "content": "what is the weather in sf"}]}

    result = agent.stream(inputs, stream_mode=["updates", "messages"])
    stream_agent_with_ui(result)

