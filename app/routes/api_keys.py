"""API key management routes.

These endpoints manage API keys themselves and therefore REQUIRE an interactive
session (cookie or Bearer). API key holders cannot manage their own keys —
revoke/rotate must happen from the web UI.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_interactive_identity
from app.models import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyResponse
from app.services.core.api_key_service import ApiKeyService

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


@router.get("", response_model=List[ApiKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    _identity=Depends(require_interactive_identity),
    db: Session = Depends(get_db),
):
    """List the current user's API keys (hashes/secrets are never returned)."""
    service = ApiKeyService(db)
    records = service.list_for_user(current_user.id)
    return [ApiKeyResponse.model_validate(r) for r in records]


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_api_key(
    payload: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    _identity=Depends(require_interactive_identity),
    db: Session = Depends(get_db),
):
    """Create a new API key for the current user.

    The raw key value is included in the response and CANNOT be retrieved later.
    """
    service = ApiKeyService(db)
    record, raw_key = service.create(current_user.id, payload.name)
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
async def revoke_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    _identity=Depends(require_interactive_identity),
    db: Session = Depends(get_db),
):
    """Revoke (soft-delete) one of the current user's API keys."""
    service = ApiKeyService(db)
    ok = service.revoke(key_id, user_id=current_user.id)
    if not ok:
        raise HTTPException(
            status_code=404, detail="API key not found or already revoked"
        )
    return None
