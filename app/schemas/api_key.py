from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=100, description="Human readable label"
    )


class ApiKeyResponse(BaseModel):
    """Public representation of an API key (never includes the raw secret)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class ApiKeyCreated(ApiKeyResponse):
    """Returned exactly ONCE on creation. Includes the raw key value."""

    key: str = Field(
        ..., description="Raw API key value. Store securely; not retrievable later."
    )


class ApiKeyList(BaseModel):
    keys: List[ApiKeyResponse]
