from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: int | None = None  # None = create new session
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: int  # actual session_id used
    kb_sources: int = 0
    personal_memories: int = 0
    profile: Optional[Dict[str, List[str]]] = None
    error: Optional[str] = None
