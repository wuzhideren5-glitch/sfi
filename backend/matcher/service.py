from __future__ import annotations

from .models import MatchRequest, MatchResponse


class MatcherService:
    async def match_profile(self, request: MatchRequest) -> MatchResponse:
        return MatchResponse(user_id=request.user_id, matches=[])
