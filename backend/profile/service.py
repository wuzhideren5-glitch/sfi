from __future__ import annotations

from .models import ProfileResponse, ProfileUpsertRequest


class ProfileService:
    async def upsert_profile(self, request: ProfileUpsertRequest) -> ProfileResponse:
        return ProfileResponse(
            user_id=request.user_id or "stub",
            profile=request.profile,
            status="stub",
        )
