from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from .models import ParseResponse
from .service import parse_resume

router = APIRouter(prefix="/parse", tags=["parser"])


@router.post("/resume", response_model=ParseResponse)
async def upload_resume(file: UploadFile = File(...)) -> ParseResponse:
    """Upload a resume PDF, parse it with AI, return structured profile."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return ParseResponse(
            filename=file.filename or "unknown",
            status="error",
            error="仅支持PDF格式简历",
        )

    file_bytes = await file.read()
    return await parse_resume(file_bytes, file.filename)
