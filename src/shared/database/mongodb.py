"""MongoDB connection utilities."""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from shared.config import settings


_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    """Get MongoDB client (singleton)."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_url)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    """Get MongoDB database."""
    return get_client()[settings.mongodb_db]


async def close_db():
    """Close MongoDB connection."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
