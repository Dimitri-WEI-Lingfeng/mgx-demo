"""Dev server 分布式锁（Redis），防止多实例/多进程并发启动冲突。"""
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio.lock import Lock

from shared.config import settings

REDIS_KEY_PREFIX = "dev_server:lock:"
LOCK_TIMEOUT = 60  # 秒，防止进程崩溃导致死锁
BLOCKING_TIMEOUT = 30  # 秒，最大等待获取锁时间

_redis_client: redis.Redis | None = None


async def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url)
    return _redis_client


@asynccontextmanager
async def dev_server_lock(workspace_id: str):
    """按 workspace_id 的 Redis 分布式锁，用于 start_dev_server 及 auto-start 防并发。"""
    r = await _get_redis()
    lock = Lock(
        r,
        f"{REDIS_KEY_PREFIX}{workspace_id}",
        timeout=LOCK_TIMEOUT,
        blocking_timeout=BLOCKING_TIMEOUT,
    )
    async with lock:
        yield
