"""知识库管理。"""

import traceback
from agents.web_app_team.rag.vector_store import VectorStoreManager
from agents.web_app_team.rag.retriever import KnowledgeRetriever
from agents.web_app_team.rag.default_knowledge import (
    load_default_knowledge,
    load_fallback_content,
)


class DefaultKnowledgeBase:
    """默认内存知识库：无向量存储时的兜底实现，返回固定 prompt 内容。"""

    COLLECTIONS = {
        "architecture_patterns": "架构设计模式",
        "api_design": "API 设计最佳实践",
        "react_docs": "React 文档",
        "nextjs_docs": "Next.js 文档",
        "fastapi_docs": "FastAPI 文档",
        "testing_practices": "测试最佳实践",
        "code_examples": "代码示例库",
    }

    def __init__(self):
        self._knowledge = load_default_knowledge()
        self._fallback = load_fallback_content()

    async def search_knowledge(
        self,
        query: str,
        category: str = None,
        top_k: int = 5,
        use_compression: bool = True
    ) -> list[dict]:
        """搜索知识库，返回固定的兜底内容（异步接口，实际为内存查找）。"""
        if category:
            content = self._knowledge.get(category, self._fallback)
            return [{"source": category, "content": content}]
        # 无 category 时返回通用兜底
        return [{"source": "default", "content": self._fallback}]


class KnowledgeBase:
    """知识库管理器。
    
    管理各种类型的知识库，支持初始化、搜索和更新。
    """
    
    # 预定义的知识库集合
    COLLECTIONS = {
        "architecture_patterns": "架构设计模式",
        "api_design": "API 设计最佳实践",
        "react_patterns": "React 设计模式",
        "fastapi_docs": "FastAPI 文档",
        "nextjs_docs": "Next.js 文档",
        "testing_practices": "测试最佳实践",
        "code_examples": "代码示例库",
    }
    
    def __init__(self, vector_store_manager: VectorStoreManager):
        """初始化知识库。
        
        Args:
            vector_store_manager: 向量存储管理器
        """
        self.vsm = vector_store_manager
        self.retriever = KnowledgeRetriever(vector_store_manager)
    
    def initialize_knowledge_bases(self):
        """初始化知识库（从预定义文档加载）。
        
        注意：这个方法应该在首次启动时调用一次，或者定期更新知识库。
        """
        print("初始化知识库...")
        
        # 1. 架构设计模式
        arch_patterns = [
            "MVC 模式：Model-View-Controller 分离关注点，将数据模型、视图和控制器分离，提高代码可维护性。",
            "分层架构：表示层（UI）、业务逻辑层（Service）、数据访问层（DAO），每层职责明确。",
            "微服务架构：将应用拆分为多个独立服务，每个服务可独立部署和扩展。",
            "事件驱动架构：通过事件解耦服务，提高系统灵活性和可扩展性。",
            "CQRS 模式：命令查询职责分离，读写操作使用不同的模型和数据存储。",
            "Repository 模式：封装数据访问逻辑，提供统一的数据操作接口。",
        ]
        try:
            self.vsm.get_or_create_store("architecture_patterns", arch_patterns)
            print("✓ 架构设计模式知识库已加载")
        except Exception as e:
            print(f"✗ 架构设计模式加载失败: {e}")
            traceback.print_exc()
        
        # 2. API 设计最佳实践
        api_design = [
            "RESTful API 设计原则：资源导向、HTTP 方法语义化（GET 查询、POST 创建、PUT 更新、DELETE 删除）。",
            "API 版本控制：推荐使用 URL 版本（/api/v1/users）或 Header 版本（Accept: application/vnd.api+json; version=1）。",
            "错误处理：返回统一的错误响应格式，包含 error_code、message 和 details。",
            "分页和过滤：使用查询参数（?page=1&limit=20&sort=created_at&filter=status:active）。",
            "认证和授权：使用 JWT Token 或 OAuth2，在 Header 中传递（Authorization: Bearer <token>）。",
            "API 文档：使用 OpenAPI/Swagger 规范，自动生成文档。",
        ]
        try:
            self.vsm.get_or_create_store("api_design", api_design)
            print("✓ API 设计最佳实践知识库已加载")
        except Exception as e:
            print(f"✗ API 设计加载失败: {e}")
            traceback.print_exc()
        
        # 3. React 设计模式
        react_patterns = [
            "组件组合：使用 props.children 和组合模式构建灵活的组件。",
            "Hooks 模式：使用 useState、useEffect、useContext 等 Hooks 管理状态和副作用。",
            "自定义 Hooks：封装可复用的逻辑，例如 useFetch、useLocalStorage。",
            "Context API：用于跨组件共享状态，避免 prop drilling。",
            "受控组件：表单输入由 React state 控制，value 和 onChange 配合使用。",
            "高阶组件（HOC）：包装组件以增强功能，例如 withAuth、withLoading。",
        ]
        try:
            self.vsm.get_or_create_store("react_patterns", react_patterns)
            print("✓ React 设计模式知识库已加载")
        except Exception as e:
            print(f"✗ React 模式加载失败: {e}")
            traceback.print_exc()
        
        # 4. 测试最佳实践
        testing_practices = [
            "测试金字塔：70% 单元测试、20% 集成测试、10% E2E 测试，平衡覆盖率和速度。",
            "TDD（测试驱动开发）：先写测试再写代码，确保代码可测试性。",
            "单元测试原则：测试应该独立、快速、可重复，使用 mock 隔离依赖。",
            "测试覆盖率：aim for 80%+ 代码覆盖率，重点关注关键业务逻辑。",
            "集成测试：测试模块间的集成，验证数据流和接口正确性。",
            "E2E 测试：模拟真实用户场景，测试完整流程。",
            "测试命名：测试名称应清楚说明测试内容，例如 test_user_login_with_invalid_credentials_should_fail。",
        ]
        try:
            self.vsm.get_or_create_store("testing_practices", testing_practices)
            print("✓ 测试最佳实践知识库已加载")
        except Exception as e:
            print(f"✗ 测试实践加载失败: {e}")
            traceback.print_exc()
        
        print("知识库初始化完成")
    
    async def search_knowledge(
        self,
        query: str,
        category: str = None,
        top_k: int = 5,
        use_compression: bool = True
    ) -> list[dict]:
        """搜索知识库。

        Args:
            query: 搜索查询
            category: 指定类别（可选）
            top_k: 返回结果数量
            use_compression: 是否使用压缩检索

        Returns:
            搜索结果列表，每个结果包含 source 和 content
        """
        if category and category in self.COLLECTIONS:
            # 在特定类别中搜索
            results = await self.retriever.aretrieve(
                query,
                category,
                top_k,
                use_compression
            )
            return [{"source": category, "content": r} for r in results]
        else:
            # 在所有类别中搜索
            all_results = []
            for collection in self.COLLECTIONS.keys():
                try:
                    results = await self.retriever.aretrieve(
                        query,
                        collection,
                        top_k=2,
                        use_compression=False  # 跨集合搜索时不压缩，避免太慢
                    )
                    all_results.extend([
                        {"source": collection, "content": r, "score": 0.0}
                        for r in results
                    ])
                except Exception as e:
                    print(f"Error searching {collection}: {e}")
                    traceback.print_exc()
                    continue

            # 返回前 K 个结果
            return all_results[:top_k]
    
    def add_custom_knowledge(
        self,
        category: str,
        documents: list[str],
        metadatas: list[dict] = None
    ):
        """添加自定义知识到知识库。
        
        Args:
            category: 类别名称
            documents: 文档列表
            metadatas: 元数据列表
        """
        self.vsm.add_documents(category, documents, metadatas)
        
        # 更新集合列表
        if category not in self.COLLECTIONS:
            self.COLLECTIONS[category] = f"自定义知识库：{category}"
