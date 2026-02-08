"""Session agent running state via Redis lease."""
import redis

from shared.config.settings import settings


class SessionRunningService:
    """Manage session is_running state using Redis keys with TTL.
    
    Key: session:agent:running:{session_id}
    TTL: agent_task_timeout_seconds + TTL_EXTRA (auto-expire on worker crash)
    """

    KEY_PREFIX = "session:agent:running:"
    TTL_EXTRA = 60  # seconds beyond agent_task_timeout_seconds

    def __init__(self):
        """Initialize Redis client."""
        self.redis = redis.from_url(settings.redis_url)

    def _key(self, session_id: str) -> str:
        """Build Redis key for session."""
        return f"{self.KEY_PREFIX}{session_id}"

    def set_running(self, session_id: str, ttl: int | None = None) -> None:
        """Mark session as running (agent task in progress).
        
        Args:
            session_id: Session ID
            ttl: Optional TTL in seconds; default uses agent_task_timeout_seconds + TTL_EXTRA
        """
        if ttl is None:
            ttl = settings.agent_task_timeout_seconds + self.TTL_EXTRA
        key = self._key(session_id)
        self.redis.setex(key, ttl, "1")

    def clear_running(self, session_id: str) -> None:
        """Clear running state (agent task finished).
        
        Args:
            session_id: Session ID
        """
        self.redis.delete(self._key(session_id))

    def is_running(self, session_id: str) -> bool:
        """Check if session has agent task running.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if key exists
        """
        return bool(self.redis.exists(self._key(session_id)))

    def is_running_batch(self, session_ids: list[str]) -> dict[str, bool]:
        """Check running state for multiple sessions.
        
        Args:
            session_ids: List of session IDs
            
        Returns:
            dict mapping session_id to is_running
        """
        if not session_ids:
            return {}
        keys = [self._key(sid) for sid in session_ids]
        pipe = self.redis.pipeline()
        for key in keys:
            pipe.exists(key)
        results = pipe.execute()
        return {sid: bool(exists) for sid, exists in zip(session_ids, results)}
