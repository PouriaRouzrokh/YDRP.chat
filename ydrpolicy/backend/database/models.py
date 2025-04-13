# ydrpolicy/backend/database/models.py
from datetime import datetime
import logging
from typing import List, Optional

from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Float,
    UniqueConstraint,
    Index,
    func,
    JSON,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.ext.asyncio import AsyncAttrs

# Use declarative_base from sqlalchemy.orm
from sqlalchemy.orm import declarative_base, relationship, mapped_column, Mapped, selectinload

# Initialize logger
logger = logging.getLogger(__name__)

# Import config
from ydrpolicy.backend.config import config

# Import for pgvector
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    logger.warning("pgvector not installed. Vector type will be mocked.")

    # For type checking and testing without pgvector installed
    class Vector:
        def __init__(self, dimensions):
            self.dimensions = dimensions
            logger.warning(f"Mock Vector created with dimensions: {dimensions}")

        def __call__(self, *args, **kwargs):
            # Mock the behavior when used as a type hint or column type
            return self  # Or return a mock column type if necessary


# Base class for all models
Base = declarative_base(cls=(AsyncAttrs,))


class User(Base):
    """User model for authentication and access control."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()  # Use func.now() for database default
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    chats: Mapped[List["Chat"]] = relationship("Chat", back_populates="user")
    policy_updates: Mapped[List["PolicyUpdate"]] = relationship("PolicyUpdate", back_populates="admin")

    def __repr__(self):
        return f"<User {self.email}>"


class Policy(Base):
    """
    Policy document model. Stores metadata, full markdown, and full text content.
    Text content is used for chunking and embedding.
    """

    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Title extracted from folder name (part before _<timestamp>)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Optional description, potentially extracted or added later
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Placeholder for original source URL if available
    source_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # Full original markdown content from content.md
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)
    # Cleaned text content from content.txt (used for chunking)
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    # Metadata, e.g., scrape timestamp, source folder name
    policy_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()  # Use func.now() for database default
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),  # Use func.now() for database default
        onupdate=func.now(),  # Use func.now() for database onupdate
    )
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    # Chunks derived from this policy's text_content
    chunks: Mapped[List["PolicyChunk"]] = relationship(
        "PolicyChunk", back_populates="policy", cascade="all, delete-orphan"  # Delete chunks when policy is deleted
    )
    # Images associated with this policy
    images: Mapped[List["Image"]] = relationship(
        "Image", back_populates="policy", cascade="all, delete-orphan"  # Delete images when policy is deleted
    )
    # History of updates to this policy
    updates: Mapped[List["PolicyUpdate"]] = relationship("PolicyUpdate", back_populates="policy")

    # Indexes
    __table_args__ = (
        # Unique constraint on title to prevent duplicates during initialization
        UniqueConstraint("title", name="uix_policy_title"),
        Index("idx_policies_search_vector", search_vector, postgresql_using="gin"),
    )

    def __repr__(self):
        return f"<Policy id={self.id} title='{self.title}'>"


class PolicyChunk(Base):
    """
    Chunks of policy documents (derived from Policy.text_content) with embeddings.
    """

    __tablename__ = "policy_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(
        Integer,
        # Ensure foreign key constraint deletes chunks if policy is deleted
        ForeignKey("policies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Index of the chunk within the policy's text_content
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # The actual text content of the chunk
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional metadata specific to the chunk
    chunk_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    # Embedding vector for the chunk content
    embedding = mapped_column(Vector(config.RAG.EMBEDDING_DIMENSIONS), nullable=True)
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()  # Use func.now() for database default
    )

    # Relationships
    policy: Mapped["Policy"] = relationship("Policy", back_populates="chunks")

    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint("policy_id", "chunk_index", name="uix_policy_chunk_index"),
        Index("idx_policy_chunks_search_vector", search_vector, postgresql_using="gin"),
        # Index for vector similarity search (adjust parameters as needed)
        Index(
            "idx_policy_chunks_embedding",
            embedding,
            postgresql_using="ivfflat",  # Or 'hnsw' depending on needs and pgvector version
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},  # Use cosine similarity
        ),
    )

    def __repr__(self):
        policy_repr = f"policy_id={self.policy_id}" if not self.policy else f"policy='{self.policy.title}'"
        return f"<PolicyChunk id={self.id} {policy_repr} index={self.chunk_index}>"


class Image(Base):
    """
    Metadata about images associated with a policy.
    Images themselves are stored in the filesystem within the policy folder.
    """

    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(
        Integer,
        # Ensure foreign key constraint deletes images if policy is deleted
        ForeignKey("policies.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Filename as found in the policy folder (e.g., "img-1.png")
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # Relative path within the processed policy folder (usually same as filename)
    relative_path: Mapped[str] = mapped_column(String(512), nullable=False)
    # Optional metadata like dimensions, alt text if extracted
    image_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()  # Use func.now() for database default
    )

    # Relationships
    policy: Mapped["Policy"] = relationship("Policy", back_populates="images")

    # Constraints
    __table_args__ = (UniqueConstraint("policy_id", "filename", name="uix_policy_image_filename"),)

    def __repr__(self):
        policy_repr = f"policy_id={self.policy_id}" if not self.policy else f"policy='{self.policy.title}'"
        return f"<Image id={self.id} {policy_repr} filename='{self.filename}'>"


class Chat(Base):
    """Chat session model."""

    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), index=True, nullable=False  # Assuming ON DELETE RESTRICT/NO ACTION by default
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()  # Use func.now() for database default
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),  # Use func.now() for database default
        onupdate=func.now(),  # Use func.now() for database onupdate
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="chats")
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="chat", cascade="all, delete-orphan"  # Delete messages when chat is deleted
    )

    def __repr__(self):
        return f"<Chat id={self.id} user_id={self.user_id}>"


class Message(Base):
    """Message model for chat interactions."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(
        Integer,
        # Ensure foreign key constraint deletes messages if chat is deleted
        ForeignKey("chats.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # 'user', 'assistant', or 'system'
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()  # Use func.now() for database default
    )

    # Relationships
    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")
    tool_usages: Mapped[List["ToolUsage"]] = relationship(
        "ToolUsage", back_populates="message", cascade="all, delete-orphan"  # Delete tool usage when message is deleted
    )

    def __repr__(self):
        chat_repr = f"chat_id={self.chat_id}" if not self.chat else f"chat_id={self.chat.id}"
        return f"<Message id={self.id} {chat_repr} role='{self.role}'>"


class ToolUsage(Base):
    """Tool usage tracking for assistant messages."""

    __tablename__ = "tool_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        Integer,
        # Ensure foreign key constraint deletes tool usage if message is deleted
        ForeignKey("messages.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # 'rag', 'keyword_search', etc.
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Tool input parameters
    input: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Tool output
    output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()  # Use func.now() for database default
    )
    # Time taken in seconds
    execution_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    message: Mapped["Message"] = relationship("Message", back_populates="tool_usages")

    def __repr__(self):
        message_repr = f"message_id={self.message_id}" if not self.message else f"message_id={self.message.id}"
        return f"<ToolUsage id={self.id} {message_repr} tool='{self.tool_name}'>"


class PolicyUpdate(Base):
    """Log of policy updates."""

    __tablename__ = "policy_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Admin who performed the action (nullable if done by system/script)
    admin_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True  # Keep log even if user deleted
    )
    # Policy affected (nullable if policy is deleted later)
    policy_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("policies.id", ondelete="SET NULL"),  # Keep log even if policy deleted
        nullable=True,
        index=True,
    )
    # 'create', 'update', 'delete'
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # Details of what was changed
    details: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()  # Use func.now() for database default
    )

    # Relationships
    admin: Mapped[Optional["User"]] = relationship("User", back_populates="policy_updates")
    policy: Mapped[Optional["Policy"]] = relationship("Policy", back_populates="updates")

    def __repr__(self):
        policy_repr = f"policy_id={self.policy_id}" if self.policy_id else "policy_id=None"
        admin_repr = f"admin_id={self.admin_id}" if self.admin_id else "admin_id=None"
        return f"<PolicyUpdate id={self.id} {policy_repr} {admin_repr} action='{self.action}'>"


# Function to create/update trigger functions for tsvector columns
def create_search_vector_trigger():
    """Return list of SQL statements for creating trigger functions for updating search vectors."""
    return [
        """
        -- Trigger function for the 'policies' table
        CREATE OR REPLACE FUNCTION policies_search_vector_update() RETURNS trigger AS $$
        BEGIN
            -- Combine title (A), description (B), and text_content (C)
            -- Use coalesce to handle potential NULL values
            NEW.search_vector = setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
                                setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'B') ||
                                setweight(to_tsvector('english', COALESCE(NEW.text_content, '')), 'C');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """,
        """
        -- Drop existing trigger before creating a new one to avoid errors
        DROP TRIGGER IF EXISTS policies_search_vector_trigger ON policies;
        """,
        """
        -- Create the trigger for INSERT or UPDATE operations on 'policies'
        CREATE TRIGGER policies_search_vector_trigger
        BEFORE INSERT OR UPDATE ON policies
        FOR EACH ROW EXECUTE FUNCTION policies_search_vector_update();
        """,
        """
        -- Trigger function for the 'policy_chunks' table
        CREATE OR REPLACE FUNCTION policy_chunks_search_vector_update() RETURNS trigger AS $$
        BEGIN
            -- Use only the chunk's content for its search vector
            NEW.search_vector = to_tsvector('english', COALESCE(NEW.content, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """,
        """
        -- Drop existing trigger before creating a new one to avoid errors
        DROP TRIGGER IF EXISTS policy_chunks_search_vector_trigger ON policy_chunks;
        """,
        """
        -- Create the trigger for INSERT or UPDATE operations on 'policy_chunks'
        CREATE TRIGGER policy_chunks_search_vector_trigger
        BEFORE INSERT OR UPDATE ON policy_chunks
        FOR EACH ROW EXECUTE FUNCTION policy_chunks_search_vector_update();
        """,
    ]
