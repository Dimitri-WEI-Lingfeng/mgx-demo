"""Project Manager Agent - 任务拆解。"""

from collections.abc import Sequence

from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentMiddleware
from langchain_openai import ChatOpenAI

from agents.web_app_team.tools.workspace_tools import read_file, write_file, list_files
from agents.web_app_team.tools.workflow_decision import workflow_decision
from agents.web_app_team.prompts.project_manager import PJM_SYSTEM_PROMPT


def create_pjm_agent(
    llm: ChatOpenAI,
    callbacks: list = None,
    middleware: Sequence[AgentMiddleware] = (),
):
    """创建 Project Manager Agent。
    
    Args:
        llm: 语言模型
        callbacks: 回调函数列表
    
    Returns:
        Compiled agent graph
    
    Note:
        需要通过 context.set_context() 设置 AgentContext 后才能使用
    """
    tools = [read_file, write_file, list_files, workflow_decision]
    
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=PJM_SYSTEM_PROMPT,
        middleware=list(middleware),
    )
    return agent
