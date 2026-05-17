from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class MatchRequest(BaseModel):
    user_id: str
    target_roles: List[str] = Field(default_factory=list)


class MatchResponse(BaseModel):
    user_id: str
    matches: List[Dict[str, str]] = Field(default_factory=list)
