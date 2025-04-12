from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    create_async_engine as _create_async_engine,
    AsyncEngine, AsyncSession, async_sessionmaker
)

from ydrpolicy.backend.config import config
from ydrpolicy.backend.logger import BackendLogger

# Initialize logger
logger = BackendLogger(name=__name__, path=config.LOGGING.FILE)

# Global engine instance
_engine: Optional[AsyncEngine] = None


def get_async_engine() -> AsyncEngine:
    """
    Get or create a SQLAlchemy AsyncEngine instance.
    
    This function implements the singleton pattern to ensure
    only one engine is created throughout the application.
    
    Returns:
        AsyncEngine: The SQLAlchemy engine instance.
    """
    global _engine
    
    if _engine is None:
        logger.info("Creating new database engine")
        
        _engine = _create_async_engine(
            str(config.DATABASE.DATABASE_URL),
            echo=False,  # Set to True for debugging SQL queries
            pool_size=config.DATABASE.POOL_SIZE,
            max_overflow=config.DATABASE.MAX_OVERFLOW,
            pool_timeout=config.DATABASE.POOL_TIMEOUT,
            pool_recycle=config.DATABASE.POOL_RECYCLE,
            pool_pre_ping=True,  # Verify connection before using from pool
        )
        
        logger.info("Database engine created successfully")
    
    return _engine


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Create a new AsyncSession as an async context manager.
    
    Usage:
    ```
    async with get_async_session() as session:
        result = await session.execute(...)
    ```
    
    Yields:
        AsyncSession: A SQLAlchemy async session.
    """
    engine = get_async_engine()
    async_session_factory = async_sessionmaker(
        engine, 
        expire_on_commit=False,
        class_=AsyncSession
    )
    
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
            logger.debug("Session committed successfully")
        except Exception as e:
            await session.rollback()
            logger.error(f"Session rolled back due to error: {str(e)}")
            raise


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a new AsyncSession. 
    
    This function is mainly used for dependency injection in FastAPI.
    
    Yields:
        AsyncSession: A SQLAlchemy async session.
    
    Example:
    ```
    @app.get("/items/")
    async def get_items(session: AsyncSession = Depends(get_session)):
        ...
    ```
    """
    engine = get_async_engine()
    async_session_factory = async_sessionmaker(
        engine, 
        expire_on_commit=False,
        class_=AsyncSession
    )
    
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def close_db_connection() -> None:
    """
    Close the database connection pool.
    
    This function should be called when the application shuts down.
    """
    global _engine
    
    if _engine is not None:
        logger.info("Closing database connection pool")
        await _engine.dispose()
        _engine = None
        logger.info("Database connection pool closed")