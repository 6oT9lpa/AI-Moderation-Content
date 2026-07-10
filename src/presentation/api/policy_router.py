from fastapi import APIRouter, Depends, Query

from src.application.api_moderation_service import ApiModerationService
from src.contracts.api.effective_policy_response_schema import EffectivePolicyResponseSchema
from src.presentation.api.dependencies import get_api_service, get_correlation_id, require_internal_api_key

router = APIRouter(prefix="/policies", tags=["policies"], dependencies=[Depends(require_internal_api_key)])


@router.get("/effective", response_model=EffectivePolicyResponseSchema)
async def effective_policy(
    platform: str = Query(default="discord", min_length=1, max_length=32, pattern=r"^[a-z0-9_-]+$"),
    guild_id: str | None = Query(default=None, min_length=1, max_length=32, pattern=r"^[0-9A-Za-z_-]+$"),
    channel_id: str | None = Query(default=None, min_length=1, max_length=32, pattern=r"^[0-9A-Za-z_-]+$"),
    service: ApiModerationService = Depends(get_api_service),
    correlation_id: str = Depends(get_correlation_id),
) -> EffectivePolicyResponseSchema:
    return await service.effective_policies(platform, guild_id, channel_id, correlation_id)
