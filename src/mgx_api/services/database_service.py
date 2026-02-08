"""Database query service."""
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

from shared.config import settings


class DatabaseService:
    """Service for querying app databases."""
    
    def __init__(self):
        """Initialize DatabaseService."""
        self.client = AsyncIOMotorClient(settings.mongodb_url)
        # Apps use a separate database for their data
        self.apps_db_name = settings.mongodb_apps_db
    
    def _get_app_db(self, session_id: str):
        """Get database for a specific app/session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Database instance for the app
        """
        # Each app gets its own database named after the session_id
        # or use a shared apps database with session_id as prefix
        return self.client[self.apps_db_name]
    
    async def list_collections(self, session_id: str) -> list[dict[str, Any]]:
        """List all collections in an app's database.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of collection info with name and document count
        """
        db = self._get_app_db(session_id)
        collection_names = await db.list_collection_names()
        
        collections = []
        for name in collection_names:
            # Skip system collections
            if name.startswith("system."):
                continue
            
            # Get document count
            count = await db[name].count_documents({})
            collections.append({
                "name": name,
                "document_count": count
            })
        
        return collections
    
    async def query_collection(
        self,
        session_id: str,
        collection: str,
        filter_query: dict[str, Any],
        limit: int = 10,
        skip: int = 0
    ) -> tuple[list[dict[str, Any]], int, bool]:
        """Query a collection in an app's database.
        
        Args:
            session_id: Session ID
            collection: Collection name
            filter_query: MongoDB filter query
            limit: Maximum number of documents
            skip: Number of documents to skip
            
        Returns:
            Tuple of (documents, count, has_more)
        """
        db = self._get_app_db(session_id)
        
        # Get total count matching the filter
        total_count = await db[collection].count_documents(filter_query)
        
        # Query documents with limit and skip
        cursor = db[collection].find(filter_query).skip(skip).limit(limit)
        documents = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string for JSON serialization
        for doc in documents:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
        
        # Check if there are more documents
        has_more = (skip + len(documents)) < total_count
        
        return documents, total_count, has_more
