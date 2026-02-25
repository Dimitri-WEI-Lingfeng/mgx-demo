"""事件驱动团队工厂函数。

创建 EventDrivenOrchestrator 实例，复用现有的 Agent 创建逻辑。
"""

from __future__ import annotations

import traceback

from loguru import logger

from shared.config import settings
from agents.web_app_team.team import get_agent_llm
from agents.web_app_team.agents import (
    create_boss_agent,
    create_pm_agent,
    create_architect_agent,
    create_pjm_agent,
    create_engineer_agent,
    create_qa_agent,
)
from agents.web_app_team.middleware import DevServerEventMiddleware
from agents.web_app_team.event_driven.orchestrator import EventDrivenOrchestrator


def create_event_driven_team(
    framework: str,
    workspace_id: str = "",
    callbacks: list | None = None,
) -> EventDrivenOrchestrator:
    """创建事件驱动的 web app 开发团队。

    复用现有的 Agent 创建逻辑（prompts、tools、middleware），
    但用 EventDrivenOrchestrator 替代 LangGraph 顺序工作流。

    Args:
        framework: 目标框架（nextjs, fastapi-vite）
        workspace_id: 工作区 ID
        callbacks: 回调函数列表（如 Langfuse）

    Returns:
        EventDrivenOrchestrator 实例
    """
    logger.info(f"\n=== 创建事件驱动 Web App 开发团队 ===")
    logger.info(f"Workspace: {workspace_id}")
    logger.info(f"Framework: {framework}")
    logger.info(f"Default Model: {settings.agent_default_model}")

    # RAG 初始化
    if settings.enable_rag:
        try:
            from agents.web_app_team.rag import VectorStoreManager, KnowledgeBase
            from agents.web_app_team.tools.rag_tools import set_knowledge_base

            vsm = VectorStoreManager(settings.vector_store_path)
            kb = KnowledgeBase(vsm)
            existing = vsm.list_collections()
            if not existing:
                kb.initialize_knowledge_bases()
            set_knowledge_base(kb)
            logger.info("✓ RAG 模块已初始化")
        except Exception as e:
            logger.warning(f"✗ RAG 初始化失败: {e}")
    else:
        logger.info("RAG 模块未启用")

    # Middleware
    middleware_list = []
    if settings.enable_context_compression:
        try:
            from agents.web_app_team.middleware import SummarizationMiddleware
            compression_mw = SummarizationMiddleware(
                model=settings.agent_summary_model,
                trigger=("tokens", settings.context_max_tokens),
                keep=("messages", settings.context_recent_window),
                trim_tokens_to_summarize=settings.context_trim_tokens_to_summarize,
            )
            middleware_list = [compression_mw]
        except Exception as e:
            logger.warning(f"✗ 上下文压缩初始化失败: {e}")

    # 创建各 Agent（复用现有逻辑）
    logger.info("创建 Agents...")

    boss = create_boss_agent(llm=get_agent_llm("boss", callbacks), callbacks=callbacks, middleware=middleware_list)
    pm = create_pm_agent(llm=get_agent_llm("pm", callbacks), callbacks=callbacks, middleware=middleware_list)
    architect = create_architect_agent(llm=get_agent_llm("architect", callbacks), framework=framework, callbacks=callbacks, middleware=middleware_list)
    pjm = create_pjm_agent(llm=get_agent_llm("pjm", callbacks), callbacks=callbacks, middleware=middleware_list)

    engineer_middleware = middleware_list + [DevServerEventMiddleware()]
    engineer = create_engineer_agent(llm=get_agent_llm("engineer", callbacks), framework=framework, callbacks=callbacks, middleware=engineer_middleware)
    qa = create_qa_agent(llm=get_agent_llm("qa", callbacks), callbacks=callbacks, middleware=middleware_list)

    logger.info("✓ 所有 Agent 创建完成")

    # 创建 Orchestrator
    orchestrator = EventDrivenOrchestrator(
        boss_agent=boss,
        pm_agent=pm,
        architect_agent=architect,
        pjm_agent=pjm,
        engineer_agent=engineer,
        qa_agent=qa,
        framework=framework,
        workspace_id=workspace_id,
    )

    logger.info("✓ 事件驱动团队创建完成\n")
    return orchestrator
