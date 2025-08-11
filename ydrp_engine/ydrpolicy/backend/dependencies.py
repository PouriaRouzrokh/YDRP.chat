# ydrpolicy/backend/dependencies.py
"""
FastAPI dependencies for authentication and other common utilities.
"""
import logging
from typing import Annotated  # Use Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ydrpolicy.backend.utils.auth_utils import decode_token
from ydrpolicy.backend.database.engine import get_session
from ydrpolicy.backend.database.models import User
from ydrpolicy.backend.database.repository.users import UserRepository
from ydrpolicy.backend.schemas.auth import TokenData  # Import TokenData schema

logger = logging.getLogger(__name__)

# OAuth2PasswordBearer scheme points to the /auth/token endpoint
# This dependency extracts the token from the "Authorization: Bearer <token>" header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: AsyncSession = Depends(get_session),
) -> User:
    """
    Dependency to get the current user from the JWT token.
    Verifies token validity and existence of the user in the database.

    Raises:
        HTTPException(401): If token is invalid, expired, or user not found.

    Returns:
        The authenticated User database model object.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None:
        logger.warning("Token decoding failed or token expired.")
        raise credentials_exception

    # Use TokenData Pydantic model for validation and clarity
    try:
        token_data = TokenData(**payload)
    except Exception:  # Catch Pydantic validation error or other issues
        logger.warning("Token payload validation failed.")
        raise credentials_exception

    if token_data.email is None:
        logger.warning("Token payload missing 'sub' (email).")
        raise credentials_exception

    user_repo = UserRepository(session)
    user = await user_repo.get_by_email(token_data.email)
    if user is None:
        logger.warning(f"User '{token_data.email}' from token not found in database.")
        raise credentials_exception

    logger.debug(f"Authenticated user via token: {user.email}")
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Dependency that builds on get_current_user to ensure the user is active.
    (Currently, your User model doesn't have `is_active`, so this is placeholder).
    If you add `is_active` to the User model, uncomment the check.

    Raises:
        HTTPException(400): If the user is inactive.

    Returns:
        The active authenticated User database model object.
    """
    # if not current_user.is_active: # UNCOMMENT if you add is_active to User model
    #     logger.warning(f"Inactive user attempted access: {current_user.email}")
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user
