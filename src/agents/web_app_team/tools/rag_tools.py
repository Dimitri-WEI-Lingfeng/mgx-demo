"""RAG 工具 - 知识库查询。"""

import traceback
from langchain.tools import tool
from agents.web_app_team.rag.knowledge_base import KnowledgeBase, DefaultKnowledgeBase


# 全局知识库实例（在团队初始化时创建）
_knowledge_base: KnowledgeBase | None = None

# 默认兜底知识库（单例）
_default_kb = DefaultKnowledgeBase()


def set_knowledge_base(kb: KnowledgeBase):
    """设置全局知识库实例。
    
    Args:
        kb: 知识库实例
    """
    global _knowledge_base
    _knowledge_base = kb


def get_knowledge_base() -> KnowledgeBase | DefaultKnowledgeBase:
    """获取全局知识库实例。
    
    当未设置知识库时，返回 DefaultKnowledgeBase 作为兜底（返回固定 prompt 内容）。
    
    Returns:
        知识库实例
    """
    return _knowledge_base if _knowledge_base is not None else _default_kb


@tool
async def search_architecture_patterns(query: str) -> str:
    """搜索架构设计模式和最佳实践。

    Args:
        query: 搜索查询，例如"微服务通信方式"、"API 设计原则"、"分层架构"

    Returns:
        相关的架构模式和设计建议
    """
    try:
        kb = get_knowledge_base()
        results = await kb.search_knowledge(
            query,
            category="architecture_patterns",
            top_k=3
        )

        if not results:
            return "未找到相关的架构模式信息"

        return "\n\n".join([r["content"] for r in results])

    except Exception as e:
        traceback.print_exc()
        return f"搜索架构模式时出错：{str(e)}"


@tool
async def search_framework_docs(framework: str, query: str) -> str:
    """搜索框架文档和 API 用法。
    
    Args:
        framework: 框架名称（react, nextjs, fastapi）
        query: 搜索查询，例如"useState 用法"、"路由配置"、"数据库连接"
    
    Returns:
        相关的框架文档和代码示例
    """
    try:
        kb = get_knowledge_base()
        collection = f"{framework.lower()}_docs"
        results = await kb.search_knowledge(query, category=collection, top_k=3)

        if not results:
            return f"未找到 {framework} 相关文档，建议使用 search_web 搜索官方文档"
        
        return "\n\n".join([r["content"] for r in results])
    
    except Exception as e:
        traceback.print_exc()
        return f"搜索框架文档时出错：{str(e)}。建议使用 search_web 搜索官方文档。"


@tool
async def search_testing_practices(query: str) -> str:
    """搜索测试策略和最佳实践。
    
    Args:
        query: 搜索查询，例如"单元测试覆盖率"、"E2E 测试策略"、"mock 技巧"
    
    Returns:
        相关的测试实践和建议
    """
    try:
        kb = get_knowledge_base()
        results = await kb.search_knowledge(
            query,
            category="testing_practices",
            top_k=3
        )

        if not results:
            return "未找到相关的测试实践信息"
        
        return "\n\n".join([r["content"] for r in results])
    
    except Exception as e:
        traceback.print_exc()
        return f"搜索测试实践时出错：{str(e)}"


@tool
async def search_code_examples(framework: str, component: str) -> str:
    """搜索代码示例和常见用法。

    Args:
        framework: 框架名称（react, nextjs, fastapi）
        component: 组件或功能名称，例如"用户认证"、"表单验证"

    Returns:
        相关的代码示例
    """
    try:
        kb = get_knowledge_base()
        query = f"{framework} {component} 代码示例"
        results = await kb.search_knowledge(query, category="code_examples", top_k=2)
        if not results:
            collection = f"{framework.lower()}_docs"
            results = await kb.search_knowledge(query, category=collection, top_k=2)
        
        if not results:
            return f"未找到 {framework} {component} 的代码示例，建议使用 search_web 搜索"
        
        return "\n\n".join([r["content"] for r in results])
    
    except Exception as e:
        traceback.print_exc()
        return f"搜索代码示例时出错：{str(e)}"


@tool
async def search_api_design_best_practices(query: str) -> str:
    """搜索 API 设计最佳实践。

    Args:
        query: 搜索查询，例如"RESTful API"、"错误处理"、"版本控制"

    Returns:
        相关的 API 设计建议
    """
    try:
        kb = get_knowledge_base()
        results = await kb.search_knowledge(
            query,
            category="api_design",
            top_k=3
        )
        
        if not results:
            return "未找到相关的 API 设计最佳实践"
        
        return "\n\n".join([r["content"] for r in results])
    
    except Exception as e:
        traceback.print_exc()
        return f"搜索 API 设计实践时出错：{str(e)}"
