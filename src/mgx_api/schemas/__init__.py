"""MGX API schemas module."""
from .session import SessionCreate, SessionResponse
from .workspace import FileContent, FileResponse, DirectoryEntry, DirectoryResponse, FileTreeNode, FileTreeResponse
from .container import DevContainerResponse, ProdBuildResponse, ProdContainerResponse
from .agent import AgentTaskRequest, AgentTaskResponse, AgentTaskResult
from .database import DatabaseQueryRequest, DatabaseQueryResponse, CollectionInfo, CollectionsResponse

__all__ = [
    # Session
    "SessionCreate",
    "SessionResponse",
    # Workspace
    "FileContent",
    "FileResponse",
    "DirectoryEntry",
    "DirectoryResponse",
    "FileTreeNode",
    "FileTreeResponse",
    # Container
    "DevContainerResponse",
    "ProdBuildResponse",
    "ProdContainerResponse",
    # Agent
    "AgentTaskRequest",
    "AgentTaskResponse",
    "AgentTaskResult",
    # Database
    "DatabaseQueryRequest",
    "DatabaseQueryResponse",
    "CollectionInfo",
    "CollectionsResponse",
]
