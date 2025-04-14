# ydrpolicy/backend/schemas/auth.py
"""
Pydantic schemas for authentication request/response models.
"""
from pydantic import BaseModel, Field

class Token(BaseModel):
    """Response model for the /auth/token endpoint."""
    access_token: str = Field(..., description="The JWT access token.")
    token_type: str = Field(default="bearer", description="The type of token (always 'bearer').")

class TokenData(BaseModel):
    """Data payload expected within the JWT token."""
    email: str | None = Field(None, alias="sub") # Subject claim holds the email
    user_id: int | None = None # Optional: include user_id if useful