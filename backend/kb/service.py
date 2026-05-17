from __future__ import annotations

from .models import KnowledgeRecordRequest, KnowledgeRecordResponse


class KnowledgeBaseService:
    async def create_record(
        self,
        request: KnowledgeRecordRequest,
    ) -> KnowledgeRecordResponse:
        return KnowledgeRecordResponse(record_id="stub", status="stub")
