"""
Authentication module for dashboard access.
"""

import logging
from typing import Optional
from fastapi import Request, HTTPException, status, Depends, Cookie
from fastapi.responses import RedirectResponse
import hashlib
import secrets
import time

from app.config import Config, get_config

logger = logging.getLogger(__name__)

# In-memory session storage (for simplicity)
# In production, you might want to use Redis or database
active_sessions = {}
SESSION_TIMEOUT = 24 * 60 * 60  # 24 hours


def generate_session_token() -> str:
    """Generate a secure session token."""
    return secrets.token_urlsafe(32)


def hash_password(password: str) -> str:
    """Hash a password for comparison."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, config: Config) -> bool:
    """Verify password against configured dashboard password."""
    return hash_password(password) == hash_password(config.security.dashboard_password)


def create_session(user_id: str = "admin") -> str:
    """Create a new session and return session token."""
    session_token = generate_session_token()
    active_sessions[session_token] = {
        "user_id": user_id,
        "created_at": time.time(),
        "last_accessed": time.time()
    }
    return session_token


def validate_session(session_token: Optional[str]) -> bool:
    """Validate a session token."""
    if not session_token or session_token not in active_sessions:
        return False
    
    session = active_sessions[session_token]
    current_time = time.time()
    
    # Check if session has expired
    if current_time - session["created_at"] > SESSION_TIMEOUT:
        # Remove expired session
        del active_sessions[session_token]
        return False
    
    # Update last accessed time
    session["last_accessed"] = current_time
    return True


def invalidate_session(session_token: Optional[str]) -> None:
    """Invalidate a session."""
    if session_token and session_token in active_sessions:
        del active_sessions[session_token]


def cleanup_expired_sessions() -> None:
    """Clean up expired sessions."""
    current_time = time.time()
    expired_tokens = [
        token for token, session in active_sessions.items()
        if current_time - session["created_at"] > SESSION_TIMEOUT
    ]
    
    for token in expired_tokens:
        del active_sessions[token]
    
    if expired_tokens:
        logger.info(f"Cleaned up {len(expired_tokens)} expired sessions")


async def require_auth(
    request: Request,
    session_token: Optional[str] = Cookie(None, alias="session"),
    config: Config = Depends(get_config)
) -> str:
    """
    Dependency that requires authentication.
    
    Returns session token if authenticated, raises HTTPException otherwise.
    """
    # Clean up expired sessions periodically
    cleanup_expired_sessions()
    
    # Check if user is authenticated
    if validate_session(session_token):
        return session_token
    
    # If not authenticated, redirect to login page
    # We need to handle this in the route since we can't redirect from a dependency
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required"
    )


async def optional_auth(
    session_token: Optional[str] = Cookie(None, alias="session")
) -> bool:
    """
    Optional authentication dependency.
    
    Returns True if authenticated, False otherwise.
    """
    cleanup_expired_sessions()
    return validate_session(session_token)


def login_required_redirect(request: Request, session_token: Optional[str] = None) -> Optional[RedirectResponse]:
    """
    Check if login is required and return redirect response if needed.
    
    Returns None if user is authenticated, RedirectResponse to login if not.
    """
    cleanup_expired_sessions()
    
    if not validate_session(session_token):
        # Store the original URL to redirect back after login
        original_url = str(request.url)
        return RedirectResponse(f"/login?next={original_url}", status_code=status.HTTP_302_FOUND)
    
    return None