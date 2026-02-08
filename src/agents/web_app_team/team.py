"""团队工厂函数 - 创建和配置整个 Agent Team。"""

import traceback
from langchain_openai import ChatOpenAI

from shared.config import settings
from agents.web_app_team.agents import (
    create_boss_agent,
    create_pm_agent,
    create_architect_agent,
    create_pjm_agent,
    create_engineer_agent,
    create_qa_agent,
)
from agents.web_app_team.middleware import DevServerEventMiddleware
from agents.web_app_team.graph import create_team_graph


def get_agent_llm(agent_name: str, callbacks: list = None) -> ChatOpenAI:
    """获取 agent 的 LLM 实例，支持独立模型配置。
    
    Args:
        agent_name: agent 名称 (boss, pm, architect, pjm, engineer, qa)
        callbacks: 回调函数列表
    
    Returns:
        配置好的 ChatOpenAI 实例
    """
    # 获取模型配置
    model_map = {
        "boss": settings.agent_boss_model,
        "pm": settings.agent_pm_model,
        "architect": settings.agent_architect_model,
        "pjm": settings.agent_pjm_model,
        "engineer": settings.agent_engineer_model,
        "qa": settings.agent_qa_model,
    }
    
    temperature_map = {
        "boss": settings.agent_boss_temperature,
        "pm": settings.agent_pm_temperature,
        "architect": settings.agent_architect_temperature,
        "pjm": settings.agent_pjm_temperature,
        "engineer": settings.agent_engineer_temperature,
        "qa": settings.agent_qa_temperature,
    }
    
    # 使用配置的模型，如果未设置则使用默认模型
    model = model_map.get(agent_name) or settings.agent_default_model
    temperature = temperature_map.get(agent_name) if temperature_map.get(agent_name) is not None else settings.agent_default_temperature
    
    print(f"[{agent_name.upper()}] 使用模型: {model}, 温度: {temperature}")
    
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        streaming=True,
        callbacks=callbacks,
    )


def create_web_app_team(
    framework: str,
    callbacks: list = None,
):
    """创建 web app 开发团队。
    
    Args:
        framework: 目标框架（nextjs, fastapi-vite）
        callbacks: 回调函数列表（如 Langfuse）
    
    Returns:
        编译后的团队工作流图
    
    Note:
        需要通过 context.set_context() 设置 AgentContext 后才能使用
    """
    from agents.context import get_context
    
    context = get_context()
    workspace_id = context.workspace_id if context else "unknown"
    
    print(f"\n=== 创建 Web App 开发团队 ===")
    print(f"Workspace: {workspace_id}")
    print(f"Framework: {framework}")
    print(f"Default Model: {settings.agent_default_model}")
    
    # 初始化 RAG（如果启用）
    if settings.enable_rag:
        try:
            from agents.web_app_team.rag import VectorStoreManager, KnowledgeBase
            from agents.web_app_team.tools.rag_tools import set_knowledge_base
            
            print("\n初始化 RAG 模块...")
            vsm = VectorStoreManager(settings.vector_store_path)
            kb = KnowledgeBase(vsm)
            
            # 检查知识库是否已存在，如果不存在则初始化
            existing_collections = vsm.list_collections()
            if not existing_collections:
                print("首次运行，初始化知识库...")
                kb.initialize_knowledge_bases()
            else:
                print(f"加载已有知识库：{', '.join(existing_collections)}")
            
            set_knowledge_base(kb)
            print("✓ RAG 模块已初始化并就绪")
        except Exception as e:
            print(f"✗ RAG 模块初始化失败：{e}")
            traceback.print_exc()
            print("  继续使用基础功能（不含 RAG）")
    else:
        print("RAG 模块未启用（ENABLE_RAG=false）")
    
    # 上下文压缩 middleware（SummarizationMiddleware）
    middleware_list = []
    if settings.enable_context_compression:
        try:
            from agents.web_app_team.middleware import SummarizationMiddleware
            kwargs = {
                "model": settings.agent_summary_model,
                "trigger": ("tokens", settings.context_max_tokens),
                "keep": ("messages", settings.context_recent_window),
                "trim_tokens_to_summarize": settings.context_trim_tokens_to_summarize,
            }
            if settings.context_summary_prompt is not None:
                kwargs["summary_prompt"] = settings.context_summary_prompt
            compression_mw = SummarizationMiddleware(**kwargs)
            middleware_list = [compression_mw]
            print("\n上下文压缩 Middleware 已启用（SummarizationMiddleware）")
        except Exception as e:
            print(f"✗ 上下文压缩 Middleware 初始化失败：{e}")
            traceback.print_exc()
            print("  继续创建 Agents（不含压缩）")
    
    # 创建各个 agent
    print("\n创建 Agents...")
    
    boss_agent = create_boss_agent(
        llm=get_agent_llm("boss", callbacks),
        callbacks=callbacks,
        middleware=middleware_list,
    )
    print("✓ Boss Agent 创建完成")
    
    pm_agent = create_pm_agent(
        llm=get_agent_llm("pm", callbacks),
        callbacks=callbacks,
        middleware=middleware_list,
    )
    print("✓ Product Manager Agent 创建完成")
    
    architect_agent = create_architect_agent(
        llm=get_agent_llm("architect", callbacks),
        framework=framework,
        callbacks=callbacks,
        middleware=middleware_list,
    )
    print("✓ Architect Agent 创建完成")
    
    pjm_agent = create_pjm_agent(
        llm=get_agent_llm("pjm", callbacks),
        callbacks=callbacks,
        middleware=middleware_list,
    )
    print("✓ Project Manager Agent 创建完成")
    
    engineer_middleware = middleware_list + [DevServerEventMiddleware()]
    engineer_agent = create_engineer_agent(
        llm=get_agent_llm("engineer", callbacks),
        framework=framework,
        callbacks=callbacks,
        middleware=engineer_middleware,
    )
    print("✓ Engineer Agent 创建完成")
    
    qa_agent = create_qa_agent(
        llm=get_agent_llm("qa", callbacks),
        callbacks=callbacks,
        middleware=middleware_list,
    )
    print("✓ QA Agent 创建完成")
    
    # 构建工作流图（intent 使用默认模型做轻量意图分类）
    print("\n构建工作流图...")
    intent_llm = get_agent_llm("boss", callbacks)  # 复用 boss 配置，intent 分类轻量
    team_graph = create_team_graph(
        boss_agent=boss_agent,
        pm_agent=pm_agent,
        architect_agent=architect_agent,
        pjm_agent=pjm_agent,
        engineer_agent=engineer_agent,
        qa_agent=qa_agent,
        intent_llm=intent_llm,
    )
    print("✓ 工作流图创建完成")
    
    print("\n=== 团队创建成功 ===\n")
    
    return team_graph
