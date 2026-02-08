"""Database initialization utilities."""
import asyncio

from mgx_api.dao import EventDAO, MessageDAO
from shared.database import get_db


async def init_indexes():
    """Initialize database indexes for optimal performance.
    
    This should be called during application startup.
    """
    print("Creating database indexes...")
    
    # Create indexes for events collection
    event_dao = EventDAO()
    await event_dao.create_indexes()
    print("✓ Event indexes created")
    
    # Create indexes for messages collection
    message_dao = MessageDAO()
    await message_dao.create_indexes()
    print("✓ Message indexes created")
    
    print("Database initialization complete!")


async def verify_indexes():
    """Verify that all required indexes exist."""
    db = get_db()
    
    # Check events collection indexes
    event_indexes = await db.events.index_information()
    print("\nEvents collection indexes:")
    for idx_name, idx_info in event_indexes.items():
        print(f"  - {idx_name}: {idx_info}")
    
    # Check messages collection indexes
    message_indexes = await db.messages.index_information()
    print("\nMessages collection indexes:")
    for idx_name, idx_info in message_indexes.items():
        print(f"  - {idx_name}: {idx_info}")


async def main():
    """Main initialization function."""
    await init_indexes()
    await verify_indexes()


if __name__ == "__main__":
    asyncio.run(main())
