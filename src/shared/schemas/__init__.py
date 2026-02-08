"""Shared schemas for MGX platform."""
from .event import Event, EventData, EventType
from .message import ContentPart, ContentPartType, Message
from .sse import (
    DeltaEvent,
    ErrorEvent,
    FinishEvent,
    MessageEvent,
    SSEEvent,
    StatusEvent,
    event_to_sse,
)

__all__ = [
    # Event schemas
    "Event",
    "EventData",
    "EventType",
    # Message schemas
    "Message",
    "ContentPart",
    "ContentPartType",
    # SSE schemas
    "SSEEvent",
    "DeltaEvent",
    "MessageEvent",
    "StatusEvent",
    "ErrorEvent",
    "FinishEvent",
    "event_to_sse",
]
