"""SSE (Server-Sent Events) protocol schemas."""
import json
from typing import Any

from pydantic import BaseModel, Field


class SSEEvent(BaseModel):
    """Base SSE event model.
    
    Follows the Server-Sent Events specification:
    https://html.spec.whatwg.org/multipage/server-sent-events.html
    """
    
    event: str = Field(..., description="Event type")
    id: str = Field(..., description="Event ID (used for resuming from last event)")
    data: dict[str, Any] = Field(..., description="Event data payload")
    
    def to_sse(self) -> str:
        """Convert to SSE format string.
        
        SSE format:
            event: <event_type>
            id: <event_id>
            data: <json_data>
            
            (two newlines required at the end)
        
        Returns:
            str: SSE formatted string
        """
        lines = [
            f"event: {self.event}",
            f"id: {self.id}",
            f"data: {json.dumps(self.data, ensure_ascii=False)}",
            "",  # SSE requires two newlines
        ]
        return "\n".join(lines) + "\n"
    
    class Config:
        json_schema_extra = {
            "example": {
                "event": "message_delta",
                "id": "evt_123abc",
                "data": {
                    "event_type": "message_delta",
                    "delta": "Hello",
                    "trace_id": "trace_123",
                    "run_id": "run_456"
                }
            }
        }


class DeltaEvent(SSEEvent):
    """Delta event for LLM token streaming.
    
    Used when streaming incremental LLM output token by token.
    """
    
    def __init__(self, **data):
        if "event" not in data:
            data["event"] = "delta"
        super().__init__(**data)


class MessageEvent(SSEEvent):
    """Message event for complete messages.
    
    Used when a complete message is ready (e.g., after tool execution).
    """
    
    def __init__(self, **data):
        if "event" not in data:
            data["event"] = "message"
        super().__init__(**data)


class StatusEvent(SSEEvent):
    """Status event for agent status updates.
    
    Used for agent lifecycle events like start, end, error.
    """
    
    def __init__(self, **data):
        if "event" not in data:
            data["event"] = "status"
        super().__init__(**data)


class ErrorEvent(SSEEvent):
    """Error event for error notifications.
    
    Used when an error occurs during agent execution.
    """
    
    def __init__(self, **data):
        if "event" not in data:
            data["event"] = "error"
        super().__init__(**data)


class FinishEvent(SSEEvent):
    """Finish event to signal completion.
    
    Used to signal that the agent task has completed successfully.
    """
    
    def __init__(self, **data):
        if "event" not in data:
            data["event"] = "finish"
        super().__init__(**data)


# Helper function to create SSE event from Event model
def event_to_sse(event_model: Any, event_type: str | None = None) -> SSEEvent:
    """Convert an Event model to SSE event.
    
    Args:
        event_model: Event model instance
        event_type: Optional event type override
    
    Returns:
        SSEEvent: SSE event ready to be sent to client
    """
    data = {
        "event_type": str(event_model.event_type),
        "session_id": event_model.session_id,
        "timestamp": event_model.timestamp,
        **event_model.data,
    }
    
    # Add trace information if available
    if event_model.trace_id:
        data["trace_id"] = event_model.trace_id
    if event_model.observation_id:
        data["observation_id"] = event_model.observation_id
    if event_model.run_id:
        data["run_id"] = event_model.run_id
    if event_model.message_id:
        data["message_id"] = event_model.message_id
    
    # Determine event type
    if event_type is None:
        event_type = _map_event_type_to_sse(event_model.event_type)
    
    return SSEEvent(
        event=event_type,
        id=event_model.event_id,
        data=data
    )


def _map_event_type_to_sse(event_type: str) -> str:
    """Map internal event type to SSE event type.
    
    Args:
        event_type: Internal event type
    
    Returns:
        str: SSE event type
    """
    mapping = {
        "message_delta": "delta",
        "message_complete": "message",
        "agent_start": "status",
        "agent_end": "status",
        "agent_error": "error",
        "llm_start": "status",
        "llm_stream": "delta",
        "llm_end": "status",
        "tool_start": "status",
        "tool_end": "status",
        "custom": "custom",
        "finish": "finish",
    }
    return mapping.get(event_type, "message")
