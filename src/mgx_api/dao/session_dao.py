"""Session Data Access Object."""
from typing import Any

from shared.database import get_db
from .base import BaseDAO


class SessionDAO(BaseDAO):
    """Session DAO implementation."""
    
    def __init__(self):
        """Initialize SessionDAO."""
        self.collection_name = "sessions"
    
    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Create a new session.
        
        Args:
            data: Session data to insert
            
        Returns:
            Created session document
        """
        db = get_db()
        await db[self.collection_name].insert_one(data)
        return data
    
    async def find_by_id(self, session_id: str) -> dict[str, Any] | None:
        """
        Find a session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session document or None
        """
        db = get_db()
        return await db[self.collection_name].find_one({"session_id": session_id})
    
    async def update(self, session_id: str, data: dict[str, Any]) -> bool:
        """
        Update a session.
        
        Args:
            session_id: Session ID
            data: Update data
            
        Returns:
            True if updated, False otherwise
        """
        db = get_db()
        result = await db[self.collection_name].update_one(
            {"session_id": session_id},
            {"$set": data}
        )
        return result.modified_count > 0
    
    async def delete(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if deleted, False otherwise
        """
        db = get_db()
        result = await db[self.collection_name].delete_one({"session_id": session_id})
        return result.deleted_count > 0
    
    async def find_by_username(self, username: str) -> list[dict[str, Any]]:
        """
        Find all sessions by username.
        
        Args:
            username: Creator username
            
        Returns:
            List of session documents
        """
        db = get_db()
        cursor = db[self.collection_name].find({"creator": username})
        return await cursor.to_list(length=None)
