# ydrpolicy/backend/routers/auth.py
"""
API Router for authentication related endpoints (login/token).
"""
import logging
from typing import Annotated  # Use Annotated for Depends

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm  # For login form data
from sqlalchemy.ext.asyncio import AsyncSession

# Import utilities, models, schemas, and dependencies
from ydrpolicy.backend.utils.auth_utils import create_access_token, verify_password
from ydrpolicy.backend.database.engine import get_session
from ydrpolicy.backend.database.models import User
from ydrpolicy.backend.database.repository.users import UserRepository
from ydrpolicy.backend.schemas.auth import Token  # Define this schema next

# Import the dependency to get current user (we'll define it next)
from ydrpolicy.backend.dependencies import get_current_active_user

# Import User schema for response model
from ydrpolicy.backend.schemas.user import UserRead

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: AsyncSession = Depends(get_session),
):
    """
    Standard OAuth2 password flow - login with email and password to get a JWT.
    Uses form data (grant_type=password, username=email, password=password).
    """
    logger.info(f"Attempting login for user: {form_data.username}")
    user_repo = UserRepository(session)
    # Use email as the username field
    user = await user_repo.get_by_email(form_data.username)

    # Validate user and password
    if not user or not verify_password(form_data.password, user.password_hash):
        logger.warning(
            f"Login failed for user: {form_data.username} - Invalid credentials."
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create JWT
    # 'sub' (subject) is typically the username or user ID
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
        }  # Include user_id if needed elsewhere
    )
    logger.info(f"Login successful, token created for user: {user.email}")
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me", response_model=UserRead)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """
    Test endpoint to get current authenticated user's details.
    """
    logger.info(f"Fetching details for authenticated user: {current_user.email}")
    # UserRead schema will filter out the password hash
    return current_user
