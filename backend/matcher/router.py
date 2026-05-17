from __future__ import annotations

from fastapi import APIRouter

from .models import MatchRequest, MatchResponse
from .service import MatcherService


router = APIRouter(prefix="/match", tags=["matcher"])
service = MatcherService()


@router.post("/", response_model=MatchResponse)
async def match_profile(req: MatchRequest) -> MatchResponse:
    return await service.match_profile(req)
