# ydrpolicy/backend/api_main.py
"""
Main FastAPI application setup for the YDR Policy RAG backend.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ydrpolicy.backend.config import config
from ydrpolicy.backend.logger import logger
from ydrpolicy.backend.routers import chat as chat_router # Import the chat router
# Import other routers as needed
# from ydrpolicy.backend.routers import auth as auth_router
from ydrpolicy.backend.agent.mcp_connection import close_mcp_connection
from ydrpolicy.backend.database.engine import close_db_connection
from ydrpolicy.backend.utils.paths import ensure_directories # Import ensure_directories

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Asynchronous context manager for FastAPI lifespan events.
    Handles startup and shutdown logic.
    """
    # Startup logic
    logger.info("="*80)
    logger.info("FastAPI Application Startup Initiated...")
    logger.info(f"Mode: {'Development' if config.API.DEBUG else 'Production'}")
    logger.info(f"CORS Origins Allowed: {config.API.CORS_ORIGINS}")

    # Ensure necessary directories exist on startup
    try:
        ensure_directories()
        logger.info("Verified required directories exist.")
    except Exception as e:
        logger.error(f"Failed to ensure directories: {e}", exc_info=True)
        # Decide if this is critical and should prevent startup

    # Optional: Pre-initialize/check DB engine or MCP connection as before
    # ... (database/MCP checks can be added here if desired) ...

    logger.info("FastAPI Application Startup Complete.")
    logger.info("="*80)

    yield # Application runs here

    # Shutdown logic
    logger.info("="*80)
    logger.info("FastAPI Application Shutdown Initiated...")

    await close_mcp_connection()
    await close_db_connection()

    logger.info("FastAPI Application Shutdown Complete.")
    logger.info("="*80)


# Create FastAPI app instance
app = FastAPI(
    title="Yale Radiology Policies RAG API",
    description="API for interacting with the Yale Radiology Policy RAG system with history.",
    version="0.1.0", # Incremented version
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.API.CORS_ORIGINS if config.API.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat_router.router)
# Include other routers (e.g., for listing chats, fetching history explicitly) later

# Root endpoint
@app.get("/", tags=["Root"])
async def read_root():
    """Root endpoint providing basic API information."""
    return {
        "message": "Welcome to the Yale Radiology Policies RAG API v0.2.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
        }