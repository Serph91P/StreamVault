"""API key management routes.

These endpoints manage API keys themselves and therefore REQUIRE an interactive
session (cookie or Bearer). API key holders cannot manage their own keys —
revoke/rotate must happen from the web UI.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request

from app.database import SessionLocal
from app.models import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyResponse
from app.services.core.api_key_service import ApiKeyService
from app.services.core.auth_service import AuthService

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


def _resolve_session_user(request: Request) -> User:
    """Resolve the User behind the current cookie/Bearer session.

    The global AuthMiddleware has already validated that *some* form of auth is
    present; here we still re-resolve the User because the middleware doesn't
    expose it on the request. We intentionally REJECT API-key auth for these
    endpoints to prevent a stolen key from being used to mint more keys.
    """
    session_token = request.cookies.get("session")
    if not session_token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            session_token = auth_header[7:]

    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Interactive session required to manage API keys",
        )

    import hashlib
    from app.models import Session as DbSession

    token_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()

    with SessionLocal() as db:
        sess = db.query(DbSession).filter(DbSession.token == token_hash).first()
        if not sess:
            raise HTTPException(
                status_code=401,
                detail="Interactive session required to manage API keys",
            )
        user = db.query(User).filter(User.id == sess.user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        # Detach so the caller can use it after the session closes
        db.expunge(user)
        return user


@router.get("", response_model=List[ApiKeyResponse])
async def list_api_keys(request: Request):
    """List the current user's API keys (hashes/secrets are never returned)."""
    user = _resolve_session_user(request)
    with SessionLocal() as db:
        service = ApiKeyService(db)
        records = service.list_for_user(user.id)
        return [ApiKeyResponse.model_validate(r) for r in records]


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_api_key(payload: ApiKeyCreate, request: Request):
    """Create a new API key for the current user.

    The raw key value is included in the response and CANNOT be retrieved later.
    """
    user = _resolve_session_user(request)
    with SessionLocal() as db:
        service = ApiKeyService(db)
        record, raw_key = service.create(user.id, payload.name)
        return ApiKeyCreated(
            id=record.id,
            name=record.name,
            key_prefix=record.key_prefix,
            created_at=record.created_at,
            last_used_at=record.last_used_at,
            revoked_at=record.revoked_at,
            key=raw_key,
        )


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(key_id: int, request: Request):
    """Revoke (soft-delete) one of the current user's API keys."""
    user = _resolve_session_user(request)
    with SessionLocal() as db:
        service = ApiKeyService(db)
        ok = service.revoke(key_id, user_id=user.id)
        if not ok:
            raise HTTPException(status_code=404, detail="API key not found or already revoked")
    return None
