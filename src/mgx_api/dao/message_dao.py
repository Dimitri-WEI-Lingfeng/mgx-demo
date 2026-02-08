"""Message Data Access Object."""
import time
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from shared.database import get_db
from shared.schemas import ContentPart, ContentPartType, Message

from .base import BaseDAO


class MessageDAO(BaseDAO):
    """Message DAO implementation for agent messages."""
    
    def __init__(self):
        """Initialize MessageDAO."""
        self.collection_name = "messages"
    
    async def create_message(self, message: Message) -> Message:
        """Create a new message.
        
        Args:
            message: Message instance to create
        
        Returns:
            Message: Created message
        """
        message_data = message.model_dump()
        
        # Content field is already properly serialized by pydantic
        # (can be str or list[ContentPart])
        
        db = get_db()
        await db[self.collection_name].insert_one(message_data)
        
        return message
    
    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new message (BaseDAO interface).
        
        Args:
            data: Message data
        
        Returns:
            dict: Created message document
        """
        db = get_db()
        
        # Generate IDs if not provided
        if "message_id" not in data:
            data["message_id"] = str(uuid.uuid4())
        if "timestamp" not in data:
            data["timestamp"] = time.time()
        
        await db[self.collection_name].insert_one(data)
        return data
    
    async def find_by_id(self, message_id: str) -> dict[str, Any] | None:
        """Find a message by ID.
        
        Args:
            message_id: Message ID
        
        Returns:
            Message document or None
        """
        db = get_db()
        return await db[self.collection_name].find_one({"message_id": message_id})
    
    async def update(self, message_id: str, data: dict[str, Any]) -> bool:
        """Update a message.
        
        Args:
            message_id: Message ID
            data: Update data
        
        Returns:
            True if updated, False otherwise
        """
        db = get_db()
        result = await db[self.collection_name].update_one(
            {"message_id": message_id},
            {"$set": data}
        )
        return result.modified_count > 0
    
    async def delete(self, message_id: str) -> bool:
        """Delete a message.
        
        Args:
            message_id: Message ID
        
        Returns:
            True if deleted, False otherwise
        """
        db = get_db()
        result = await db[self.collection_name].delete_one({"message_id": message_id})
        return result.deleted_count > 0
    
    async def get_session_messages(
        self,
        session_id: str,
        limit: int = 1000
    ) -> list[Message]:
        """Get all messages for a session.
        
        Args:
            session_id: Session ID
            limit: Maximum number of messages to return
        
        Returns:
            List of messages ordered by timestamp
        """
        db = get_db()
        
        cursor = db[self.collection_name].find(
            {"session_id": session_id}
        ).sort("timestamp", 1).limit(limit)
        
        messages_data = await cursor.to_list(length=limit)
        return [Message(**msg_data) for msg_data in messages_data]

    async def get_session_messages_paginated(
        self,
        session_id: str,
        limit: int = 100,
        last_message_id: str | None = None,
        before_message_id: str | None = None,
    ) -> list[Message]:
        """Get session messages with cursor-based pagination.
        
        - If both are None: return the most recent n messages.
        - If before_message_id is not None: return n messages BEFORE that message
          (timestamp < before_message's timestamp).
        - If last_message_id is not None (and before_message_id is None): return
          n messages starting from that message (timestamp >= last_message's timestamp).
        
        Args:
            session_id: Session ID
            limit: Maximum number of messages to return
            last_message_id: Cursor message ID (None for recent messages)
            before_message_id: Return n messages before this message (exclusive)
        
        Returns:
            List of messages in chronological order (oldest first)
        """
        db = get_db()

        if before_message_id is not None:
            # 查询 before_message_id 之前的 n 条消息（不包含该消息）
            msg_doc = await db[self.collection_name].find_one(
                {"session_id": session_id, "message_id": before_message_id}
            )
            if msg_doc is None:
                # 找不到该消息，fallback 到最近 n 条
                cursor = db[self.collection_name].find(
                    {"session_id": session_id}
                ).sort("timestamp", -1).limit(limit)
                messages_data = await cursor.to_list(length=limit)
                messages = [Message(**msg_data) for msg_data in reversed(messages_data)]
            else:
                ts = msg_doc["timestamp"]
                cursor = db[self.collection_name].find(
                    {"session_id": session_id, "timestamp": {"$lt": ts}}
                ).sort("timestamp", -1).limit(limit)
                messages_data = await cursor.to_list(length=limit)
                messages = [Message(**msg_data) for msg_data in reversed(messages_data)]
            return messages

        if last_message_id is None:
            # 查询最近的 n 条消息：按时间倒序取 limit 条，再反转成 chronological
            cursor = db[self.collection_name].find(
                {"session_id": session_id}
            ).sort("timestamp", -1).limit(limit)
            messages_data = await cursor.to_list(length=limit)
            messages = [Message(**msg_data) for msg_data in reversed(messages_data)]
        else:
            # 查询从 last_message_id 开始的历史 n 条消息
            msg_doc = await db[self.collection_name].find_one(
                {"session_id": session_id, "message_id": last_message_id}
            )
            if msg_doc is None:
                # 找不到该消息，fallback 到最近 n 条
                cursor = db[self.collection_name].find(
                    {"session_id": session_id}
                ).sort("timestamp", -1).limit(limit)
                messages_data = await cursor.to_list(length=limit)
                messages = [Message(**msg_data) for msg_data in reversed(messages_data)]
            else:
                ts = msg_doc["timestamp"]
                cursor = db[self.collection_name].find(
                    {"session_id": session_id, "timestamp": {"$gte": ts}}
                ).sort("timestamp", 1).limit(limit)
                messages_data = await cursor.to_list(length=limit)
                messages = [Message(**msg_data) for msg_data in messages_data]
        
        return messages
    
    async def get_message_tree(
        self,
        session_id: str,
        root_message_id: str | None = None
    ) -> list[Message]:
        """Get message tree starting from a root message.
        
        Args:
            session_id: Session ID
            root_message_id: Root message ID (None for root messages)
        
        Returns:
            List of messages in tree order
        """
        db = get_db()
        
        # Start with root messages or messages with specific parent
        query = {
            "session_id": session_id,
            "parent_id": root_message_id
        }
        
        cursor = db[self.collection_name].find(query).sort("timestamp", 1)
        messages_data = await cursor.to_list(length=None)
        messages = [Message(**msg_data) for msg_data in messages_data]
        
        # Recursively get children
        result = []
        for message in messages:
            result.append(message)
            children = await self.get_message_tree(session_id, message.message_id)
            result.extend(children)
        
        return result
    
    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> list[dict[str, str]]:
        """Get conversation history in format suitable for LLM.
        
        Args:
            session_id: Session ID
            limit: Maximum number of messages
        
        Returns:
            List of messages in {"role": ..., "content": ...} format
        """
        messages = await self.get_session_messages(session_id, limit)
        
        result = []
        for msg in messages:
            # Convert content to string if it's a list of ContentPart
            if isinstance(msg.content, list):
                # Extract text from content parts
                text_parts = []
                for part in msg.content:
                    if part.type == ContentPartType.TEXT and part.text:
                        text_parts.append(part.text)
                    elif part.type == ContentPartType.TOOL_RESULT and part.tool_result:
                        text_parts.append(str(part.tool_result))
                content_str = " ".join(text_parts)
            else:
                content_str = msg.content
            
            result.append({"role": msg.role, "content": content_str})
        
        return result
    
    async def create_indexes(self):
        """Create indexes for the messages collection.
        
        This should be called during application initialization.
        """
        db = get_db()
        
        # Compound index for session_id + timestamp
        await db[self.collection_name].create_index(
            [("session_id", 1), ("timestamp", 1)]
        )
        
        # Index for message_id
        await db[self.collection_name].create_index("message_id", unique=True)
        
        # Index for parent_id (for tree queries)
        await db[self.collection_name].create_index("parent_id")
        
        # Index for trace_id (for langfuse integration)
        await db[self.collection_name].create_index("trace_id")
