"""
app/admin/dependencies.py
─────────────────────────
Authorization dependencies for admin routes.
"""

from fastapi import Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.models.user import User


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    FastAPI dependency that enforces admin role.

    Returns the current authenticated user if they have is_admin=True.
    Otherwise raises 403 Forbidden.

    Usage:
      @router.post("/admin/ingredients")
      async def create_ingredient(current_admin: User = Depends(get_current_admin)):
          ...
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user
