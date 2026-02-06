"""
Better Auth session validation for FastAPI integration.

This module provides middleware to validate Better Auth sessions from Next.js
by checking the session cookie against the ba_session table.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

logger = logging.getLogger(__name__)

# Better Auth cookie name
BETTER_AUTH_SESSION_COOKIE = "better-auth.session_token"


async def get_better_auth_session(request: Request) -> Optional[str]:
    """
    Extract Better Auth session token from cookies.

    Better Auth cookie format is "token.signature" - we only need the token
    part for database lookup.

    Returns:
        Session token string or None if not present
    """
    cookie_value = request.cookies.get(BETTER_AUTH_SESSION_COOKIE)
    if not cookie_value:
        return None

    # Cookie format: "token.signature" - extract just the token
    return cookie_value.split(".")[0]


async def validate_session_token(session_token: str, db: Session) -> Optional[dict]:
    """
    Validate a Better Auth session token against the database.

    Args:
        session_token: The session token from the cookie
        db: Database session

    Returns:
        Dictionary with user info if valid, None otherwise
    """
    if not session_token:
        return None

    # Query ba_session and ba_user tables to validate session
    query = text("""
        SELECT
            s.id as session_id,
            s.user_id as ba_user_id,
            s.expires_at,
            u.email,
            u.name,
            u.is_active,
            u.is_superuser
        FROM ba_session s
        JOIN ba_user u ON s.user_id = u.id
        WHERE s.token = :token
        AND s.expires_at > NOW()
        AND u.is_active = true
    """)

    result = db.execute(query, {"token": session_token}).fetchone()

    if not result:
        return None

    return {
        "session_id": result.session_id,
        "ba_user_id": result.ba_user_id,
        "email": result.email,
        "name": result.name,
        "is_active": result.is_active,
        "is_superuser": result.is_superuser,
    }


async def get_current_user_ba(request: Request, db: Session = Depends(get_db)) -> str:
    """
    Get current authenticated user from Better Auth session.

    This is the main dependency to use for protected routes.
    Returns the ba_user_id as a string.

    Raises:
        HTTPException: If session is invalid or expired
    """
    session_token = await get_better_auth_session(request)

    if not session_token:
        logger.debug("No Better Auth session cookie found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session_data = await validate_session_token(session_token, db)

    if not session_data:
        logger.debug("Invalid or expired Better Auth session")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return session_data["ba_user_id"]


async def get_current_user_ba_optional(
    request: Request, db: Session = Depends(get_db)
) -> Optional[str]:
    """
    Get current authenticated user if available (optional auth).

    Returns None if no valid session, doesn't raise exception.
    Useful for endpoints that work with or without authentication.
    """
    session_token = await get_better_auth_session(request)

    if not session_token:
        return None

    session_data = await validate_session_token(session_token, db)

    if not session_data:
        return None

    return session_data["ba_user_id"]


async def get_current_user_ba_full(request: Request, db: Session = Depends(get_db)) -> dict:
    """
    Get full user data from Better Auth session.

    Returns complete user info dict including email, name, etc.

    Raises:
        HTTPException: If session is invalid or expired
    """
    session_token = await get_better_auth_session(request)

    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session_data = await validate_session_token(session_token, db)

    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return session_data


async def get_current_user_hybrid(request: Request, db: Session = Depends(get_db)) -> str:
    """
    Get current authenticated user from either Better Auth or legacy JWT.

    This provides backward compatibility during migration by trying
    Better Auth first, then falling back to legacy JWT tokens.

    Returns the user ID as a string (either ba_user_id or legacy user.id).

    Raises:
        HTTPException: If no valid authentication found
    """
    # Try Better Auth session first
    session_token = await get_better_auth_session(request)
    if session_token:
        session_data = await validate_session_token(session_token, db)
        if session_data:
            # Find user by ba_user_id and return the legacy user.id
            query = text("SELECT id FROM users WHERE ba_user_id = :ba_user_id")
            result = db.execute(query, {"ba_user_id": session_data["ba_user_id"]}).fetchone()
            if result:
                return str(result.id)

            # User exists in Better Auth but not linked - try by email
            query = text("SELECT id FROM users WHERE email = :email")
            result = db.execute(query, {"email": session_data["email"]}).fetchone()
            if result:
                # Auto-link the user
                update_query = text("UPDATE users SET ba_user_id = :ba_user_id WHERE id = :id")
                db.execute(
                    update_query,
                    {"ba_user_id": session_data["ba_user_id"], "id": result.id},
                )
                db.commit()
                return str(result.id)

            # Create new user record for Better Auth user
            from app.models.user import User

            user = User(
                email=session_data["email"],
                full_name=session_data.get("name") or "",
                hashed_password="",  # No password - using Better Auth
                is_active=True,
                ba_user_id=session_data["ba_user_id"],
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return str(user.id)

    # Fall back to legacy JWT
    from app.core.security import get_current_user

    try:
        return await get_current_user(request)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_user_id_from_ba_user(ba_user_id: str, db: Session) -> Optional[int]:
    """
    Get the legacy user.id from a ba_user_id.

    This is used during the migration period to map Better Auth users
    to existing users in the users table.

    Args:
        ba_user_id: The Better Auth user ID
        db: Database session

    Returns:
        The legacy user ID (integer) or None if not linked
    """
    query = text("""
        SELECT id FROM users WHERE ba_user_id = :ba_user_id
    """)

    result = db.execute(query, {"ba_user_id": ba_user_id}).fetchone()

    if result:
        return result.id
    return None


async def get_current_user_id(request: Request, db: Session = Depends(get_db)) -> int:
    """
    Get the legacy integer user ID from Better Auth session.

    This dependency provides backward compatibility with existing code
    that expects integer user IDs.

    Raises:
        HTTPException: If session is invalid or user not linked
    """
    ba_user_id = await get_current_user_ba(request, db)

    user_id = get_user_id_from_ba_user(ba_user_id, db)

    if user_id is None:
        # User exists in Better Auth but not linked to legacy users table
        logger.warning(f"Better Auth user {ba_user_id} not linked to legacy users table")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not properly configured. Please contact support.",
        )

    return user_id
