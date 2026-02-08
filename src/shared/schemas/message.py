"""Message schema for multimodal agent messages."""
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ContentPartType(str, Enum):
    """Content part types for multimodal messages."""
    
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


class ContentPart(BaseModel):
    """Content part for multimodal messages.
    
    Supports various content types and can be extended by adding new types.
    """
    
    type: ContentPartType = Field(..., description="Type of content part")
    
    # For TEXT
    text: str | None = Field(None, description="Text content")
    
    # For IMAGE
    image_url: str | None = Field(None, description="Image URL")
    
    # For FILE
    file_url: str | None = Field(None, description="File URL")
    
    # For TOOL_CALL/TOOL_RESULT
    tool_call_id: str | None = Field(None, description="Tool call ID")
    tool_name: str | None = Field(None, description="Tool name")
    tool_args: dict[str, Any] | None = Field(None, description="Tool arguments")
    tool_result: Any | None = Field(None, description="Tool execution result")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "text",
                    "text": "Hello, how can I help you?"
                },
                {
                    "type": "tool_call",
                    "tool_call_id": "call_123",
                    "tool_name": "get_weather",
                    "tool_args": {"city": "San Francisco"}
                },
                {
                    "type": "tool_result",
                    "tool_call_id": "call_123",
                    "tool_result": "It's sunny in San Francisco"
                }
            ]
        }


class Message(BaseModel):
    """Message model supporting multimodal content.
    
    Compatible with langchain message structure and supports message trees
    through parent_id relationships.
    """
    
    message_id: str = Field(..., description="Unique message ID (UUID)")
    session_id: str = Field(..., description="Session ID this message belongs to")
    parent_id: str | None = Field(None, description="Parent message ID for forming message trees")
    agent_name: str | None = Field(None, description="Name of the agent that created this message")
    
    # Basic fields (langchain compatible)
    role: str = Field(..., description="Message role: system/user/assistant/tool")
    content: str | list[ContentPart] = Field(
        ..., 
        description="Message content - can be plain text or list of multimodal content parts"
    )
    
    # Tool calling support (langchain compatible)
    tool_call_id: str | None = Field(
        None,
        description="Tool call ID (for ToolMessage role, identifies which tool call this is responding to)"
    )
    tool_calls: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Tool calls made by assistant (for AIMessage role, list of tools invoked)"
    )
    
    # Langchain compatible fields
    cause_by: str | None = Field(None, description="Action that triggered this message")
    sent_from: str | None = Field(None, description="Sender identification")
    send_to: list[str] = Field(default_factory=list, description="Recipients")
    
    # Langfuse trace association
    trace_id: str | None = Field(None, description="Langfuse trace ID")
    
    # Metadata
    timestamp: float = Field(..., description="Unix timestamp when message was created")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "description": "Simple assistant message with text content",
                    "message_id": "msg_123abc",
                    "session_id": "sess_456def",
                    "parent_id": None,
                    "role": "assistant",
                    "content": "It's sunny in San Francisco",
                    "tool_call_id": None,
                    "tool_calls": [],
                    "cause_by": "get_weather_tool",
                    "sent_from": "weather_agent",
                    "send_to": [],
                    "trace_id": "trace_langfuse_123",
                    "timestamp": 1704067200.0,
                    "metadata": {}
                },
                {
                    "description": "AI message with tool calls and multimodal content",
                    "message_id": "msg_456def",
                    "session_id": "sess_456def",
                    "parent_id": "msg_123abc",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "Let me check the weather for you."
                        }
                    ],
                    "tool_call_id": None,
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "name": "get_weather",
                            "args": {"city": "San Francisco", "unit": "celsius"}
                        }
                    ],
                    "cause_by": None,
                    "sent_from": "assistant_agent",
                    "send_to": [],
                    "trace_id": "trace_langfuse_123",
                    "timestamp": 1704067200.0,
                    "metadata": {}
                },
                {
                    "description": "Tool message with result as multimodal content",
                    "message_id": "msg_789ghi",
                    "session_id": "sess_456def",
                    "parent_id": "msg_456def",
                    "role": "tool",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_call_id": "call_abc123",
                            "tool_result": "Temperature: 18°C, Conditions: Sunny"
                        }
                    ],
                    "tool_call_id": "call_abc123",
                    "tool_calls": [],
                    "cause_by": "get_weather",
                    "sent_from": "tool_executor",
                    "send_to": [],
                    "trace_id": "trace_langfuse_123",
                    "timestamp": 1704067201.0,
                    "metadata": {"tool_name": "get_weather", "execution_time_ms": 125}
                }
            ]
        }
