"""Event Data Access Object."""
import time
import uuid
from typing import Any

from shared.database import get_db
from shared.schemas import Event, EventType

from .base import BaseDAO


class EventDAO(BaseDAO):
    """Event DAO implementation for agent streaming events."""
    
    def __init__(self):
        """Initialize EventDAO."""
        self.collection_name = "events"
    
    async def create_event(self, event: Event) -> Event:
        """Create a new event.
        
        Args:
            event: Event instance to create
        
        Returns:
            Event: Created event
        """
        event_data = event.model_dump()
        
        # Ensure event_type is stored as string value
        if isinstance(event_data.get("event_type"), EventType):
            event_data["event_type"] = event_data["event_type"].value
        
        db = get_db()
        await db[self.collection_name].insert_one(event_data)
        
        return event
    
    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new event (BaseDAO interface).
        
        Args:
            data: Event data
        
        Returns:
            dict: Created event document
        """
        db = get_db()
        
        # Generate IDs if not provided
        if "event_id" not in data:
            data["event_id"] = str(uuid.uuid4())
        if "timestamp" not in data:
            data["timestamp"] = time.time()
        
        await db[self.collection_name].insert_one(data)
        return data
    
    async def find_by_id(self, event_id: str) -> dict[str, Any] | None:
        """Find an event by ID.
        
        Args:
            event_id: Event ID
        
        Returns:
            Event document or None
        """
        db = get_db()
        return await db[self.collection_name].find_one({"event_id": event_id})
    
    async def update(self, event_id: str, data: dict[str, Any]) -> bool:
        """Update an event.
        
        Args:
            event_id: Event ID
            data: Update data
        
        Returns:
            True if updated, False otherwise
        """
        db = get_db()
        result = await db[self.collection_name].update_one(
            {"event_id": event_id},
            {"$set": data}
        )
        return result.modified_count > 0
    
    async def delete(self, event_id: str) -> bool:
        """Delete an event.
        
        Args:
            event_id: Event ID
        
        Returns:
            True if deleted, False otherwise
        """
        db = get_db()
        result = await db[self.collection_name].delete_one({"event_id": event_id})
        return result.deleted_count > 0
    
    async def get_new_events(
        self,
        session_id: str,
        after_event_id: str | None = None,
        after_timestamp: float | None = None,
        limit: int = 100
    ) -> list[Event]:
        """Get new events after a specific event ID or timestamp.
        
        This is used for polling new events in SSE streaming.
        
        Args:
            session_id: Session ID
            after_event_id: Get events after this event ID (by timestamp)
            after_timestamp: Get events after this Unix timestamp (takes precedence)
            limit: Maximum number of events to return
        
        Returns:
            List of events ordered by timestamp
        """
        db = get_db()
        
        # Build query
        query: dict[str, Any] = {"session_id": session_id}
        
        if after_timestamp is not None:
            query["timestamp"] = {"$gt": after_timestamp}
        elif after_event_id:
            # Get the timestamp of the after_event
            after_event = await db[self.collection_name].find_one(
                {"event_id": after_event_id}
            )
            if after_event:
                query["timestamp"] = {"$gt": after_event["timestamp"]}
        
        # Fetch events ordered by timestamp
        cursor = db[self.collection_name].find(query).sort("timestamp", 1).limit(limit)
        events_data = await cursor.to_list(length=limit)
        
        return [Event(**event_data) for event_data in events_data]
    
    async def get_events_since(
        self,
        session_id: str,
        since_timestamp: float | None = None,
        limit: int = 1000
    ) -> list[Event]:
        """Get events since a specific timestamp.
        
        If since_timestamp is None, returns all events (same as get_session_events).
        
        Args:
            session_id: Session ID
            since_timestamp: Unix timestamp; None means return all events
            limit: Maximum number of events to return
        
        Returns:
            List of events ordered by timestamp
        """
        if since_timestamp is None:
            return await self.get_session_events(session_id, limit)
        
        db = get_db()
        query: dict[str, Any] = {
            "session_id": session_id,
            "timestamp": {"$gt": since_timestamp},
        }
        cursor = db[self.collection_name].find(query).sort("timestamp", 1).limit(limit)
        events_data = await cursor.to_list(length=limit)
        return [Event(**event_data) for event_data in events_data]
    
    async def get_events_after(
        self,
        session_id: str,
        after_event_id: str,
        limit: int = 1000
    ) -> list[Event]:
        """Get all events after a specific event ID.
        
        This is used for resuming SSE streaming from a specific point.
        
        Args:
            session_id: Session ID
            after_event_id: Get events after this event ID
            limit: Maximum number of events to return
        
        Returns:
            List of events ordered by timestamp
        """
        return await self.get_new_events(session_id, after_event_id, limit)
    
    async def get_session_events(
        self,
        session_id: str,
        limit: int = 1000
    ) -> list[Event]:
        """Get all events for a session.
        
        Args:
            session_id: Session ID
            limit: Maximum number of events to return
        
        Returns:
            List of events ordered by timestamp
        """
        db = get_db()
        
        cursor = db[self.collection_name].find(
            {"session_id": session_id}
        ).sort("timestamp", 1).limit(limit)
        
        events_data = await cursor.to_list(length=limit)
        return [Event(**event_data) for event_data in events_data]
    
    async def get_latest_event(
        self,
        session_id: str
    ) -> Event | None:
        """Get the latest event for a session.
        
        Args:
            session_id: Session ID
        
        Returns:
            Latest event or None
        """
        db = get_db()
        
        event_data = await db[self.collection_name].find_one(
            {"session_id": session_id},
            sort=[("timestamp", -1)]
        )
        
        return Event(**event_data) if event_data else None
    
    async def delete_old_events(
        self,
        before_timestamp: float
    ) -> int:
        """Delete events older than a specific timestamp.
        
        This is used for periodic cleanup of old events.
        
        Args:
            before_timestamp: Delete events before this timestamp
        
        Returns:
            Number of deleted events
        """
        db = get_db()
        result = await db[self.collection_name].delete_many(
            {"timestamp": {"$lt": before_timestamp}}
        )
        return result.deleted_count
    
    async def get_finish_event(
        self,
        session_id: str
    ) -> dict[str, Any] | None:
        """获取 session 的 FINISH 事件。
        
        用于 celery task 监控 agent 完成状态。
        
        Args:
            session_id: Session ID
        
        Returns:
            FINISH 事件文档或 None
        """
        db = get_db()
        
        event_data = await db[self.collection_name].find_one(
            {
                "session_id": session_id,
                "event_type": EventType.FINISH.value
            },
            sort=[("timestamp", -1)]
        )
        
        return event_data
    
    async def create_indexes(self):
        """Create indexes for the events collection.
        
        This should be called during application initialization.
        """
        db = get_db()
        
        # Compound index for session_id + timestamp (for efficient polling)
        await db[self.collection_name].create_index(
            [("session_id", 1), ("timestamp", 1)]
        )
        
        # Index for event_id (for quick lookups)
        await db[self.collection_name].create_index("event_id", unique=True)
        
        # Index for trace_id (for langfuse integration)
        await db[self.collection_name].create_index("trace_id")
        
        # Compound index for session_id + event_type (for FINISH event queries)
        await db[self.collection_name].create_index(
            [("session_id", 1), ("event_type", 1)]
        )
        
        # TTL index for automatic cleanup (optional, 7 days)
        await db[self.collection_name].create_index(
            "timestamp",
            expireAfterSeconds=7 * 24 * 60 * 60  # 7 days
        )
