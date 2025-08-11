# ydrpolicy/backend/schemas/user.py
"""
Pydantic schemas for User model representation in API responses.
"""
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    """Base schema for user attributes."""

    email: EmailStr = Field(..., description="User's unique email address.")
    full_name: str = Field(..., min_length=1, description="User's full name.")
    is_admin: bool = Field(
        default=False, description="Flag indicating admin privileges."
    )


class UserRead(UserBase):
    """Schema for reading/returning user data (excludes password)."""

    id: int = Field(..., description="Unique identifier for the user.")
    created_at: datetime = Field(
        ..., description="Timestamp when the user was created."
    )
    last_login: Optional[datetime] = Field(
        None, description="Timestamp of the last login."
    )

    # Enable ORM mode for creating from SQLAlchemy model
    model_config = ConfigDict(from_attributes=True)


# Add UserCreate, UserUpdate schemas later if needed for user management endpoints
