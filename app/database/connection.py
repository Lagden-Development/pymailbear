from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.exc import SQLAlchemyError
import os
import logging
import time
import backoff
from typing import Generator, AsyncGenerator, Optional

from app.config import Config, get_config

# Setup logging
logger = logging.getLogger(__name__)

# SQLAlchemy Base class
Base = declarative_base()

# Database connection configuration
MAX_POOL_SIZE = 20
POOL_TIMEOUT = 30
POOL_RECYCLE = 1800  # 30 minutes
POOL_PRE_PING = True
CONNECT_RETRY_COUNT = 5
CONNECT_RETRY_INTERVAL = 2  # seconds

def get_database_url(config: Config = None) -> str:
    """Get database URL from config or environment variables."""
    if config is None:
        config = get_config()

    # Check if database config exists
    if hasattr(config, "database") and config.database is not None:
        # Get values from config
        db_host = os.getenv("DB_HOST", config.database.host)
        db_port = os.getenv("DB_PORT", config.database.port)
        db_user = os.getenv("DB_USER", config.database.username)
        db_pass = os.getenv("DB_PASS", config.database.password)
        db_name = os.getenv("DB_NAME", config.database.dbname)
    else:
        # Default values if not in config
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", 3306)
        db_user = os.getenv("DB_USER", "mailbear")
        db_pass = os.getenv("DB_PASS", "mailbear")
        db_name = os.getenv("DB_NAME", "mailbear")

    # Create URL with connection parameters for better stability
    params = {
        "charset": "utf8mb4",
        "connect_timeout": "10",
    }
    
    param_str = "&".join(f"{k}={v}" for k, v in params.items())
    return f"mysql+aiomysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?{param_str}"


# Async engine and session
async_engine = None
AsyncSessionLocal = None


def database_connection_is_configured() -> bool:
    """Check if database connection has been configured."""
    return async_engine is not None and AsyncSessionLocal is not None


# Backoff decorator for database connection retries
@backoff.on_exception(
    backoff.expo,
    (SQLAlchemyError, ConnectionError),
    max_tries=CONNECT_RETRY_COUNT,
    jitter=backoff.full_jitter
)
def setup_database(database_url: Optional[str] = None):
    """
    Set up database connection with retry logic.
    
    Args:
        database_url: Optional database URL, will be fetched from config if None
    
    Raises:
        SQLAlchemyError: If unable to connect to the database after retries
    """
    global async_engine, AsyncSessionLocal

    if database_url is None:
        database_url = get_database_url()
    
    try:
        logger.info(f"Setting up database connection to {database_url.split('@')[1]}")
        
        async_engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=POOL_PRE_PING,
            pool_recycle=POOL_RECYCLE,
            pool_size=MAX_POOL_SIZE,
            max_overflow=10,
            pool_timeout=POOL_TIMEOUT
        )

        AsyncSessionLocal = sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False
        )
        
        logger.info("Database connection setup successfully")
    except Exception as e:
        logger.error(f"Error setting up database connection: {str(e)}")
        raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session with proper error handling.
    
    Yields:
        AsyncSession: SQLAlchemy async session
        
    Notes:
        This function is designed to be used as a FastAPI dependency.
        It will try to establish a database connection if none exists.
        It yields None if database is not enabled in configuration.
    """
    config = get_config()

    # Check if database is enabled
    if not getattr(config, "use_db", False):
        # If database is not enabled, yield None
        yield None
        return

    # Setup database connection if not already configured
    if not database_connection_is_configured():
        try:
            setup_database()
        except Exception as e:
            logger.error(f"Failed to set up database: {str(e)}")
            yield None
            return

    # Create session and handle errors
    session = None
    try:
        session = AsyncSessionLocal()
        yield session
        await session.commit()
    except SQLAlchemyError as e:
        if session:
            await session.rollback()
        logger.error(f"Database error: {str(e)}")
        raise
    except Exception as e:
        if session:
            await session.rollback()
        logger.error(f"Unexpected error during database operation: {str(e)}")
        raise
    finally:
        if session:
            await session.close()


async def check_database_connection() -> bool:
    """
    Check if database connection is working.
    
    Returns:
        bool: True if connection is working, False otherwise
    """
    if not database_connection_is_configured():
        try:
            setup_database()
        except Exception as e:
            logger.error(f"Failed to set up database: {str(e)}")
            return False
    
    try:
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
            return True
    except Exception as e:
        logger.error(f"Database connection check failed: {str(e)}")
        return False