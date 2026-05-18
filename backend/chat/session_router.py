"""Session API — create, list, delete user sessions."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.session_store import SessionManager, TEST_USER_ID

router = APIRouter(prefix="/api/session", tags=["session"])


def _verify_ownership(session_id: int):
    sess = SessionManager.get_session(session_id)
    if not sess or sess.get("user_id") != TEST_USER_ID:
        raise HTTPException(403, "无权访问此会话")


class SessionCreateResponse(BaseModel):
    session_id: int
    user_id: str
    title: str
    created_at: float


class SessionItem(BaseModel):
    session_id: int
    title: str
    started_at: float
    updated_at: float
    turn_count: int


class SessionListResponse(BaseModel):
    sessions: list[SessionItem]


@router.post("/create", response_model=SessionCreateResponse)
async def create_session():
    result = SessionManager.create(user_id=TEST_USER_ID)
    return SessionCreateResponse(**result)


@router.get("/list", response_model=SessionListResponse)
async def list_sessions():
    sessions = SessionManager.list_sessions(user_id=TEST_USER_ID)
    return SessionListResponse(sessions=[SessionItem(**s) for s in sessions])


@router.delete("/{session_id}")
async def delete_session(session_id: int):
    _verify_ownership(session_id)
    SessionManager.delete_session(session_id)
    return {"status": "ok", "session_id": session_id}


@router.get("/{session_id}/history")
async def get_session_history(session_id: int):
    """Get all messages in a session."""
    _verify_ownership(session_id)
    from core.session_store import SessionStore
    store = SessionStore(session_id=session_id, user_id=TEST_USER_ID)
    history = store.get_session_history()
    return {"session_id": session_id, "messages": history, "total": len(history)}
