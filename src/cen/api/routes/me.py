"""Current-user endpoint for the frontend.

Returns the authenticated operator's identity + admin flag. The frontend
uses this to hide admin-only surfaces (SOP Studio) on initial mount.

When real RBAC lands, the body grows to include roles/permissions; the
URL is stable so the swap is invisible to frontend callers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from cen.api.dependencies import get_current_user
from cen.core.models import User

router = APIRouter(tags=["me"])


@router.get("/me", response_model=User)
async def get_me(user: User = Depends(get_current_user)) -> User:
    return user
