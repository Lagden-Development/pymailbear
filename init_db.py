import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from app.database.models import Base
from app.config import get_config
from app.database.connection import get_database_url


async def init_db():
    """Initialize the database by creating all tables."""
    print("Initializing database...")

    # Get config and database URL
    config = get_config()
    database_url = get_database_url(config)

    print(f"Using database: {database_url}")

    # Create async engine
    engine = create_async_engine(database_url, echo=True)

    async with engine.begin() as conn:
        # Drop all tables if --drop flag is provided
        if len(sys.argv) > 1 and sys.argv[1] == "--drop":
            print("Dropping all tables...")
            await conn.run_sync(Base.metadata.drop_all)

        # Create all tables
        print("Creating all tables...")
        await conn.run_sync(Base.metadata.create_all)

    print("Database initialization complete!")


if __name__ == "__main__":
    asyncio.run(init_db())
