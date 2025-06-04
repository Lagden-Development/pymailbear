import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.schema import CreateTable
from sqlalchemy.sql import text

from app.config import get_config
from app.database.connection import get_database_url, Base
from app.database.models import (
    User,
    Form,
    FormDomain,
    Submission,
    FormTemplate,
    APIKey,
    Setting,
)
from app.database.repository import UserRepository
from passlib.context import CryptContext

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_tables(engine: AsyncEngine) -> None:
    """Create all tables."""
    async with engine.begin() as conn:
        logger.info("Creating database tables...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully!")


async def drop_tables(engine: AsyncEngine) -> None:
    """Drop all tables."""
    async with engine.begin() as conn:
        logger.info("Dropping database tables...")
        await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped successfully!")


async def initialize_admin_user(engine: AsyncEngine) -> None:
    """Create admin user if it doesn't exist."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    config = get_config()

    # Get admin credentials from config or use defaults
    admin_email = getattr(config, "admin_email", "admin@mailbear.local")
    admin_password = getattr(
        config, "admin_password", "admin123"
    )  # This should be changed immediately

    # Create a session
    async_session = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Check if admin exists
        from sqlalchemy import select

        query = select(User).where(User.email == admin_email)
        result = await session.execute(query)
        admin = result.scalar_one_or_none()

        if not admin:
            logger.info(f"Creating admin user: {admin_email}")
            # Hash the password
            password_hash = pwd_context.hash(admin_password)

            # Create admin user
            await UserRepository.create(
                db=session,
                email=admin_email,
                password_hash=password_hash,
                name="Admin",
                role="admin",
            )
            logger.info("Admin user created successfully!")
        else:
            logger.info("Admin user already exists")


async def initialize_database() -> None:
    """Initialize the database."""
    config = get_config()

    if not config.use_db or not config.database:
        logger.warning(
            "Database configuration not found or use_db is False. Skipping database initialization."
        )
        return

    # Get database URL
    database_url = get_database_url(config)

    # Create engine
    engine = create_async_engine(database_url, echo=config.database.echo)

    try:
        # Create tables
        await create_tables(engine)

        # Initialize admin user
        await initialize_admin_user(engine)

        logger.info("Database initialized successfully!")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(initialize_database())
