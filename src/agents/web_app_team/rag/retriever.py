"""知识检索器。"""

import traceback
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import LLMChainExtractor
from langchain_openai import ChatOpenAI
from agents.web_app_team.rag.vector_store import VectorStoreManager


class KnowledgeRetriever:
    """知识检索器。
    
    支持基本检索和压缩检索两种模式。
    """
    
    def __init__(self, vector_store_manager: VectorStoreManager, llm: ChatOpenAI = None):
        """初始化知识检索器。
        
        Args:
            vector_store_manager: 向量存储管理器
            llm: 用于压缩的 LLM（可选）
        """
        self.vsm = vector_store_manager
        self.llm = llm or ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    async def aretrieve(
        self,
        query: str,
        collection_name: str,
        top_k: int = 5,
        use_compression: bool = True
    ) -> list[str]:
        """异步检索相关文档。

        Args:
            query: 查询文本
            collection_name: 集合名称
            top_k: 返回前 K 个结果
            use_compression: 是否使用压缩检索器

        Returns:
            检索到的文档内容列表
        """
        try:
            store = self.vsm.get_or_create_store(collection_name)
            base_retriever = store.as_retriever(search_kwargs={"k": top_k})

            if use_compression:
                # 使用压缩检索器，提取与查询最相关的部分
                compressor = LLMChainExtractor.from_llm(self.llm)
                retriever = ContextualCompressionRetriever(
                    base_compressor=compressor,
                    base_retriever=base_retriever
                )
            else:
                retriever = base_retriever

            docs = await retriever.ainvoke(query)
            return [doc.page_content for doc in docs]

        except ValueError as e:
            # 集合不存在
            print(f"Collection {collection_name} not found: {e}")
            return []
        except Exception as e:
            print(f"Error retrieving from {collection_name}: {e}")
            traceback.print_exc()
            return []
    
    async def aretrieve_with_scores(
        self,
        query: str,
        collection_name: str,
        top_k: int = 5
    ) -> list[tuple[str, float]]:
        """异步检索相关文档并返回相似度分数。

        Args:
            query: 查询文本
            collection_name: 集合名称
            top_k: 返回前 K 个结果

        Returns:
            (文档内容, 相似度分数) 元组列表
        """
        try:
            store = self.vsm.get_or_create_store(collection_name)
            docs_and_scores = await store.asimilarity_search_with_score(query, k=top_k)
            return [(doc.page_content, score) for doc, score in docs_and_scores]
        except Exception as e:
            print(f"Error retrieving with scores from {collection_name}: {e}")
            traceback.print_exc()
            return []
