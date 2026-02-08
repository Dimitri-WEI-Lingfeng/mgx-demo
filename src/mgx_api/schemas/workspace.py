"""Workspace file operation schemas."""
from pydantic import BaseModel


class FileContent(BaseModel):
    """File content request."""
    content: str


class FileResponse(BaseModel):
    """File read response."""
    path: str
    content: str
    size: int


class DirectoryEntry(BaseModel):
    """Directory entry info."""
    name: str
    path: str
    is_dir: bool
    size: int | None = None


class DirectoryResponse(BaseModel):
    """Directory listing response."""
    path: str
    entries: list[DirectoryEntry]


class FileTreeNode(BaseModel):
    """Recursive file tree node."""
    name: str
    path: str
    is_dir: bool
    size: int | None = None
    children: list["FileTreeNode"] | None = None


class FileTreeResponse(BaseModel):
    """Full workspace file tree response."""
    entries: list[FileTreeNode]
