import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.core.config import settings

logger = logging.getLogger(__name__)


class MongoDB:
    def __init__(self) -> None:
        self.client: AsyncIOMotorClient | None = None
        self.database: AsyncIOMotorDatabase | None = None

    async def connect(self) -> None:
        self.client = AsyncIOMotorClient(
            settings.mongodb_url,
            serverSelectionTimeoutMS=5000,
        )
        self.database = self.client[settings.database_name]

        try:
            await self.client.admin.command("ping")
            logger.info("Connected to MongoDB database: %s", settings.database_name)
        except Exception:
            logger.exception("MongoDB connection failed.")
            await self.disconnect()
            raise

    async def disconnect(self) -> None:
        if self.client is not None:
            self.client.close()
            logger.info("MongoDB connection closed.")
        self.client = None
        self.database = None

    def get_collection(self, name: str) -> AsyncIOMotorCollection:
        if self.database is None:
            raise RuntimeError("Database is not connected.")
        return self.database[name]


mongodb = MongoDB()
