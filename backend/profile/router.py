from __future__ import annotations

from fastapi import APIRouter

from .models import ProfileResponse, ProfileUpsertRequest
from .service import ProfileService


router = APIRouter(prefix="/profile", tags=["profile"])
service = ProfileService()


@router.post("/upsert", response_model=ProfileResponse)
async def upsert_profile(req: ProfileUpsertRequest) -> ProfileResponse:
    return await service.upsert_profile(req)
