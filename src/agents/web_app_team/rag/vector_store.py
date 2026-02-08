"""向量存储管理。"""

import traceback
from pathlib import Path
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings


class VectorStoreManager:
    """向量数据库管理器。
    
    管理多个向量存储集合，每个集合存储不同类型的知识。
    """
    
    def __init__(self, persist_directory: str = "./vector_stores"):
        """初始化向量存储管理器。
        
        Args:
            persist_directory: 向量存储持久化目录
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.embeddings = OpenAIEmbeddings()
        self.stores = {}
    
    def get_or_create_store(
        self, 
        collection_name: str,
        documents: list[str] = None,
        metadatas: list[dict] = None
    ) -> Chroma:
        """获取或创建向量存储。
        
        Args:
            collection_name: 集合名称
            documents: 文档列表（创建新存储时使用）
            metadatas: 文档元数据列表
        
        Returns:
            Chroma 向量存储实例
        
        Raises:
            ValueError: 如果存储不存在且未提供文档
        """
        # 如果已经加载，直接返回
        if collection_name in self.stores:
            return self.stores[collection_name]
        
        store_path = self.persist_directory / collection_name
        
        # 尝试加载已有的存储
        if store_path.exists():
            try:
                store = Chroma(
                    collection_name=collection_name,
                    embedding_function=self.embeddings,
                    persist_directory=str(store_path)
                )
                self.stores[collection_name] = store
                return store
            except Exception as e:
                print(f"Warning: Failed to load existing store {collection_name}: {e}")
                traceback.print_exc()
        
        # 创建新存储
        if documents:
            store = Chroma.from_texts(
                texts=documents,
                metadatas=metadatas,
                embedding=self.embeddings,
                collection_name=collection_name,
                persist_directory=str(store_path)
            )
            self.stores[collection_name] = store
            return store
        
        raise ValueError(
            f"Store {collection_name} not found and no documents provided. "
            f"Please provide documents to create a new store."
        )
    
    def add_documents(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: list[dict] = None
    ):
        """添加文档到向量存储。
        
        Args:
            collection_name: 集合名称
            documents: 文档列表
            metadatas: 文档元数据列表
        """
        try:
            store = self.get_or_create_store(collection_name, documents, metadatas)
            if collection_name in self.stores and documents:
                # 如果存储已存在，添加新文档
                store.add_texts(documents, metadatas=metadatas)
        except Exception as e:
            print(f"Error adding documents to {collection_name}: {e}")
            traceback.print_exc()
            raise
    
    def delete_collection(self, collection_name: str):
        """删除向量存储集合。
        
        Args:
            collection_name: 集合名称
        """
        if collection_name in self.stores:
            del self.stores[collection_name]
        
        store_path = self.persist_directory / collection_name
        if store_path.exists():
            import shutil
            shutil.rmtree(store_path)
    
    def list_collections(self) -> list[str]:
        """列出所有向量存储集合。
        
        Returns:
            集合名称列表
        """
        collections = []
        if self.persist_directory.exists():
            for path in self.persist_directory.iterdir():
                if path.is_dir():
                    collections.append(path.name)
        return collections
