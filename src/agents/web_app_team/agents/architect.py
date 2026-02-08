"""Architect Agent - 架构设计。"""

from collections.abc import Sequence

from langchain.agents import create_agent
from langchain.agents.middleware.types import AgentMiddleware
from langchain_openai import ChatOpenAI

from agents.web_app_team.tools.workspace_tools import (
    read_file, write_file, list_files, search_in_files, create_directory
)
from agents.web_app_team.tools.rag_tools import (
    search_architecture_patterns,
    search_framework_docs,
    search_api_design_best_practices,
)
from agents.web_app_team.tools.search_tools import search_web, analyze_file_structure
from agents.web_app_team.tools.workflow_decision import workflow_decision
from agents.web_app_team.prompts.architect import ARCHITECT_SYSTEM_PROMPT


def create_architect_agent(
    llm: ChatOpenAI,
    framework: str,
    callbacks: list = None,
    middleware: Sequence[AgentMiddleware] = (),
):
    """创建 Architect Agent。
    
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
        # 搜索和分析工具
        analyze_file_structure,
        # RAG 工具
        search_architecture_patterns,
        search_framework_docs,
        search_api_design_best_practices,
        search_web,
        workflow_decision,
    ]
    
    # 将框架信息添加到 system prompt
    system_prompt = ARCHITECT_SYSTEM_PROMPT + f"\n\n目标框架：{framework}"
    
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        middleware=list(middleware),
    )
    return agent
