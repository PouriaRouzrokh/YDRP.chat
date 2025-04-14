# ydrpolicy/backend/auth_utils.py
"""
Authentication related utilities: password hashing, JWT creation/verification.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict

from jose import JWTError, jwt
from passlib.context import CryptContext

from ydrpolicy.backend.config import config

logger = logging.getLogger(__name__)

# --- Password Hashing ---
# Use CryptContext for handling password hashing and verification
# bcrypt is a good default scheme
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against a stored hash.

    Args:
        plain_password: The password entered by the user.
        hashed_password: The hash stored in the database.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Error verifying password: {e}", exc_info=True)
        return False

def hash_password(password: str) -> str:
    """
    Hashes a plain password using the configured context.

    Args:
        password: The plain text password to hash.

    Returns:
        The hashed password string.
    """
    return pwd_context.hash(password)

# --- JWT Token Handling ---

SECRET_KEY = config.API.JWT_SECRET
ALGORITHM = config.API.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = config.API.JWT_EXPIRATION

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a JWT access token.

    Args:
        data: Dictionary payload to encode (must include 'sub' for subject/username).
        expires_delta: Optional timedelta for token expiration. Defaults to config value.

    Returns:
        The encoded JWT string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    # Ensure 'sub' (subject) is present, commonly the user's email or ID
    if "sub" not in to_encode:
        logger.error("JWT 'sub' claim is missing in data for token creation.")
        raise ValueError("Missing 'sub' in JWT data")

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.debug(f"Created access token for sub: {data.get('sub')}, expires: {expire}")
    return encoded_jwt

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and verifies a JWT token.

    Args:
        token: The JWT string to decode.

    Returns:
        The decoded payload dictionary if the token is valid and not expired,
        otherwise None.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Optionally check for specific claims like 'sub' here if needed immediately
        # subject: Optional[str] = payload.get("sub")
        # if subject is None:
        #     logger.warning("Token decoded but missing 'sub' claim.")
        #     return None
        logger.debug(f"Token successfully decoded for sub: {payload.get('sub')}")
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired.")
        return None
    except JWTError as e:
        logger.warning(f"JWT decoding/validation error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error decoding token: {e}", exc_info=True)
        return None