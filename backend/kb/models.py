from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class KnowledgeRecordRequest(BaseModel):
    source_doc: Optional[str] = None
    record: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)


class KnowledgeRecordResponse(BaseModel):
    record_id: str
    status: str
