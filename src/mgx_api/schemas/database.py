"""Database query schemas."""
from typing import Any
from pydantic import BaseModel, Field


class DatabaseQueryRequest(BaseModel):
    """Database query request schema."""
    collection: str = Field(..., description="Collection name")
    filter: dict[str, Any] = Field(default_factory=dict, description="MongoDB filter query")
    limit: int = Field(default=10, ge=1, le=1000, description="Maximum number of documents")
    skip: int = Field(default=0, ge=0, description="Number of documents to skip")


class DatabaseQueryResponse(BaseModel):
    """Database query response schema."""
    collection: str
    documents: list[dict[str, Any]]
    count: int
    has_more: bool


class CollectionInfo(BaseModel):
    """Collection information schema."""
    name: str
    document_count: int


class CollectionsResponse(BaseModel):
    """Collections list response schema."""
    collections: list[CollectionInfo]
