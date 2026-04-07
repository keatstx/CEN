"""Auth stub for v1 — single shared operator password.

When `CEN_OPERATOR_PASSWORD` is empty (dev/test default), auth is
disabled and every request returns the stub default operator. When
set, the operator must POST their password to /auth/login and use the
returned token in `Authorization: Bearer <token>` on subsequent
requests.

The "token" is just the password itself in v1 — there is no JWT
signing, no rotation, no expiry. This is a prototype hook to make
sure every route accepts a User dependency, so the upgrade to real
auth in a future milestone is a swap of this module, not a route
rewrite.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from cen.api.dependencies import get_settings
from cen.config import Settings
from cen.core.models import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    if not settings.operator_password:
        # Auth disabled — return a no-op token to keep clients happy.
        return LoginResponse(access_token="dev-no-auth", token_type="bearer")
    if body.password != settings.operator_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    return LoginResponse(access_token=settings.operator_password, token_type="bearer")
