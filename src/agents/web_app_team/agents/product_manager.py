"""Product Manager Agent - PRD 编写。"""

from collections.abc import Sequence

from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentMiddleware
from langchain_openai import ChatOpenAI

from agents.web_app_team.tools.workspace_tools import read_file, write_file, list_files
from agents.web_app_team.tools.workflow_decision import workflow_decision
from agents.web_app_team.prompts.product_manager import PM_SYSTEM_PROMPT


def create_pm_agent(
    llm: ChatOpenAI,
    callbacks: list = None,
    middleware: Sequence[AgentMiddleware] = (),
):
    """创建 Product Manager Agent。
    
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
        system_prompt=PM_SYSTEM_PROMPT,
        middleware=list(middleware),
    )
    return agent
