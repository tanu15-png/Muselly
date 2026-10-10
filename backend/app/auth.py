from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ValidationError

bearer = HTTPBearer(auto_error=False)


class AuthUser(BaseModel):
    id: UUID
    email: str
    display_name: str | None = None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> AuthUser:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    settings = request.app.state.settings
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise HTTPException(503, "Authentication is not configured.")
    try:
        # Supabase verifies the access token. Never trust client session metadata.
        response = await request.app.state.auth_client.get(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
            headers={"apikey": settings.supabase_publishable_key, "Authorization": f"Bearer {credentials.credentials}"},
        )
    except httpx.RequestError:
        raise HTTPException(503, "Unable to verify sign-in. Please try again.") from None
    if response.status_code in (401, 403):
        raise HTTPException(401, "Your sign-in has expired. Please sign in again.", headers={"WWW-Authenticate": "Bearer"})
    if response.is_error:
        raise HTTPException(503, "Unable to verify sign-in. Please try again.")
    try:
        data = response.json()
        # Anonymous Supabase users must not bypass mandatory sign-in.
        if data.get("is_anonymous") or not data.get("email_confirmed_at"):
            raise HTTPException(401, "Confirm your email and sign in to continue.")
        metadata = data.get("user_metadata") or {}
        name = metadata.get("full_name") or metadata.get("name")
        return AuthUser(id=data["id"], email=data["email"], display_name=name[:200] if isinstance(name, str) else None)
    except (KeyError, ValueError, ValidationError, TypeError, AttributeError):
        raise HTTPException(401, "Invalid sign-in. Please sign in again.") from None
