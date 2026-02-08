"""Agent stop signal via Redis.

Used by mgx-api to request stop and by agent process to check if stop was requested.
Key: session:agent:stop:{session_id}
TTL: 60 seconds (in case agent never picks it up)
"""

import redis

from shared.config.settings import settings

KEY_PREFIX = "session:agent:stop:"
TTL_SECONDS = 60


def _key(session_id: str) -> str:
    return f"{KEY_PREFIX}{session_id}"


def request_stop(session_id: str) -> None:
    """Request agent to stop gracefully.

    Sets a Redis key that the agent checks during its execution loop.
    The agent will save content and exit when it sees this signal.

    Args:
        session_id: Session ID
    """
    r = redis.from_url(settings.redis_url)
    r.setex(_key(session_id), TTL_SECONDS, "1")


def is_stop_requested(session_id: str) -> bool:
    """Check if stop was requested for this session.

    Called by the agent process during its execution loop.

    Args:
        session_id: Session ID

    Returns:
        True if stop was requested
    """
    r = redis.from_url(settings.redis_url)
    return bool(r.exists(_key(session_id)))
