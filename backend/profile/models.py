from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ProfileUpsertRequest(BaseModel):
    user_id: Optional[str] = None
    profile: Dict[str, Any] = Field(default_factory=dict)


class ProfileResponse(BaseModel):
    user_id: str
    profile: Dict[str, Any]
    status: str
