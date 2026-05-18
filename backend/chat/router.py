from __future__ import annotations

from fastapi import APIRouter

from .models import ChatRequest, ChatResponse
from .service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])
service = ChatService()


@router.post("/send", response_model=ChatResponse)
async def send_message(req: ChatRequest) -> ChatResponse:
    result = await service.send_message(
        message=req.message,
        session_id=req.session_id,
        history=req.history,
    )
    return ChatResponse(**result)
