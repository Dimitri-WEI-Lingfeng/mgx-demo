"""Engineer Agent - 代码实现。"""

from collections.abc import Sequence

from agents.cli_ui import stream_agent_with_ui
from agents.context.memory import InMemoryContext
from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentMiddleware
from langchain_openai import ChatOpenAI
import loguru

from agents.web_app_team.tools.workspace_tools import (
    read_file, write_file, list_files, search_in_files, create_directory, delete_file
)
from agents.web_app_team.tools.docker_tools import (
    exec_command, install_package, get_container_logs, get_container_status,
    start_dev_server, get_dev_server_status, get_dev_server_logs, stop_dev_server
)
from agents.web_app_team.tools.rag_tools import (
    search_framework_docs,
    search_code_examples,
)
from agents.web_app_team.tools.search_tools import (
    search_web,
    find_files_by_name,
    analyze_file_structure,
)
from agents.web_app_team.tools.workflow_decision import workflow_decision
from agents.web_app_team.prompts.engineer import ENGINEER_SYSTEM_PROMPT


def create_engineer_agent(
    llm: ChatOpenAI,
    framework: str,
    callbacks: list = None,
    middleware: Sequence[AgentMiddleware] = (),
):
    """创建 Engineer Agent。
    
    Args:
        llm: 语言模型
        framework: 目标框架
        callbacks: 回调函数列表
    
    Returns:
        Compiled agent graph
    
    Note:
        需要通过 context.set_context() 设置 AgentContext 后才能使用
    """
    tools = [
        # Workspace 工具
        read_file,
        write_file,
        list_files,
        search_in_files,
        create_directory,
        delete_file,
        # Docker 工具
        exec_command,
        install_package,
        # Dev Server 管理工具
        start_dev_server,
        get_dev_server_status,
        get_dev_server_logs,
        stop_dev_server,
        # 搜索和分析工具
        find_files_by_name,
        analyze_file_structure,
        # RAG 工具
        search_framework_docs,
        search_code_examples,
        search_web,
        workflow_decision,
    ]
    
    # 将框架信息添加到 system prompt
    system_prompt = ENGINEER_SYSTEM_PROMPT + f"\n\n目标框架：{framework}"
    
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        middleware=list(middleware),
    )
    return agent





if __name__ == '__main__':

    from langchain_core.messages import HumanMessage
    from agents.context import set_context

    context = InMemoryContext(
            workspace_path='./workspace',
            auto_create_container=True,
        )
    
    async def main(): 
        # 设置上下文
        set_context(context)

        async with context:
            llm = ChatOpenAI(model="qwen3-coder-flash")

            agent = create_engineer_agent(llm, framework="nextjs")

            inputs = {"messages": [{"role": "user", "content": "how many files are there in the workspace. You can use shell command to count the number of files "}]}

            try:
                generator = agent.stream(inputs, stream_mode=["updates", "messages"])
                stream_agent_with_ui(generator)
            except Exception as e:
                loguru.logger.error(e)
                import traceback
                traceback.print_exc()

    
    import asyncio

    asyncio.run(main())