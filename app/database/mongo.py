from motor.motor_asyncio import AsyncIOMotorClient
from os import getenv
from typing import Optional

# Get MongoDB URI from environment variable
MONGO_URI = getenv("MONGO_URI", "mongodb://localhost:27017")

# Create MongoDB client
client = AsyncIOMotorClient(MONGO_URI)

# Get database instance
db = client.get_database()

# Default collection
users = db.users

async def get_collection(collection_name: str) -> Optional[AsyncIOMotorClient]:
    """Get a collection by name."""
    return db[collection_name] 