from __future__ import annotations

from fastapi import APIRouter

from .models import KnowledgeRecordRequest, KnowledgeRecordResponse
from .service import KnowledgeBaseService


router = APIRouter(prefix="/kb", tags=["kb"])
service = KnowledgeBaseService()


@router.post("/records", response_model=KnowledgeRecordResponse)
async def create_record(req: KnowledgeRecordRequest) -> KnowledgeRecordResponse:
    return await service.create_record(req)
