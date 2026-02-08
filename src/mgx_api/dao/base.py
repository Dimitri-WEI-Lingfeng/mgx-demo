"""Base DAO interface."""
from abc import ABC, abstractmethod
from typing import Any


class BaseDAO(ABC):
    """Base Data Access Object interface."""
    
    @abstractmethod
    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new document."""
        pass
    
    @abstractmethod
    async def find_by_id(self, id_value: str) -> dict[str, Any] | None:
        """Find a document by ID."""
        pass
    
    @abstractmethod
    async def update(self, id_value: str, data: dict[str, Any]) -> bool:
        """Update a document."""
        pass
    
    @abstractmethod
    async def delete(self, id_value: str) -> bool:
        """Delete a document."""
        pass
