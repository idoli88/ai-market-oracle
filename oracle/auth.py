"""
Authentication and authorization utilities for the API.
Handles password hashing, JWT token generation/validation, and user verification.
"""
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt

from oracle.config import settings

logger = logging.getLogger(__name__)

# Password hashing context
_schemes = [scheme.strip() for scheme in settings.PASSWORD_HASH_SCHEME.split(",") if scheme.strip()]
if not _schemes:
    _schemes = ["bcrypt"]
pwd_context = CryptContext(schemes=_schemes, deprecated="auto")


def token_hash(token: str) -> str:
    """SHA-256 hash of a JWT for session storage without keeping the raw token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database
    
    Returns:
        True if password matches, False otherwise
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Payload data to encode in the token (e.g., {"sub": user_id})
        expires_delta: Optional custom expiration time
    
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if "sub" in to_encode and not isinstance(to_encode["sub"], str):
        to_encode["sub"] = str(to_encode["sub"])
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRY_MINUTES)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        logger.warning(f"Token verification failed: {e}")
        return None


def get_user_id_from_token(token: str) -> Optional[int]:
    """
    Extract user ID from a JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        User ID if token is valid, None otherwise
    """
    payload = verify_token(token)
    if payload:
        sub = payload.get("sub")
        if isinstance(sub, str) and sub.isdigit():
            return int(sub)
        return sub
    return None


def verify_admin_password(username: str, password: str) -> bool:
    """
    Verify admin credentials.
    
    Args:
        username: Admin username
        password: Admin password (plain text)
    
    Returns:
        True if credentials are valid, False otherwise
    """
    if username != settings.ADMIN_USERNAME:
        return False
    
    if not settings.ADMIN_PASSWORD_HASH:
        logger.error("Admin password hash not configured!")
        return False
    
    return verify_password(password, settings.ADMIN_PASSWORD_HASH)


def check_security_settings():
    """
    Emit warnings for insecure defaults so production setups can fail fast.
    """
    if settings.JWT_SECRET_KEY == "change-this-in-production":
        logger.warning("JWT_SECRET_KEY is using the insecure default value.")
    if settings.ADMIN_PASSWORD_HASH == "":
        logger.warning("ADMIN_PASSWORD_HASH is not configured; admin login will fail.")
    if settings.PASSWORD_HASH_SCHEME == "plaintext" and not settings.DRY_RUN:
        logger.warning("PASSWORD_HASH_SCHEME is set to plaintext outside of DRY_RUN; this is insecure.")
