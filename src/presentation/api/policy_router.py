from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from src.application.api_moderation_service import ApiModerationService
from src.contracts.api.effective_policy_response_schema import EffectivePolicyResponseSchema
from src.presentation.api.dependencies import get_api_service, get_correlation_id, require_internal_api_key
from src.presentation.api.dependencies import get_media_policy_resolver
from src.application.effective_media_policy_resolver import EffectiveMediaPolicyResolver
from src.application.media_policy_conflict_error import MediaPolicyConflictError
from src.contracts.api.media_policy_schema import (
    EffectiveMediaPolicyResponseSchema,
    MediaPolicyUpdateSchema,
    MediaRuntimeStatusSchema,
)

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


@router.get("/media", response_model=EffectiveMediaPolicyResponseSchema)
async def effective_media_policy(
    request: Request,
    guild_id: str = Query(pattern=r"^[0-9]{1,32}$"),
    resolver: EffectiveMediaPolicyResolver = Depends(get_media_policy_resolver),
) -> EffectiveMediaPolicyResponseSchema:
    return _response(await resolver.resolve("discord", guild_id), request)


@router.put("/media", response_model=EffectiveMediaPolicyResponseSchema)
async def update_media_policy(
    payload: MediaPolicyUpdateSchema,
    request: Request,
    verified_guild_id: str = Header(alias="X-Verified-Guild-Id", pattern=r"^[0-9]{1,32}$"),
    actor_id: str = Header(alias="X-Actor-Id", pattern=r"^[0-9]{1,32}$"),
    resolver: EffectiveMediaPolicyResolver = Depends(get_media_policy_resolver),
) -> EffectiveMediaPolicyResponseSchema:
    try:
        effective = await resolver.save(
            platform="discord", guild_id=verified_guild_id, policy=payload.media,
            expected_revision=payload.expected_revision, updated_by=actor_id,
        )
    except MediaPolicyConflictError as exc:
        raise HTTPException(status_code=409, detail="media_policy_revision_conflict") from exc
    return _response(effective, request)


@router.delete("/media", response_model=EffectiveMediaPolicyResponseSchema)
async def reset_media_policy(
    request: Request,
    expected_revision: int = Query(ge=1),
    verified_guild_id: str = Header(alias="X-Verified-Guild-Id", pattern=r"^[0-9]{1,32}$"),
    actor_id: str = Header(alias="X-Actor-Id", pattern=r"^[0-9]{1,32}$"),
    resolver: EffectiveMediaPolicyResolver = Depends(get_media_policy_resolver),
) -> EffectiveMediaPolicyResponseSchema:
    try:
        effective = await resolver.reset(
            platform="discord", guild_id=verified_guild_id,
            expected_revision=expected_revision, updated_by=actor_id,
        )
    except MediaPolicyConflictError as exc:
        raise HTTPException(status_code=409, detail="media_policy_revision_conflict") from exc
    return _response(effective, request)


def _response(effective, request: Request) -> EffectiveMediaPolicyResponseSchema:
    container = request.app.state.container
    return EffectiveMediaPolicyResponseSchema(
        **effective.model_dump(),
        runtime=MediaRuntimeStatusSchema(
            ocr_enabled=container.ocr_enabled, ocr_ready=container.ocr_ready,
            yolo_enabled=container.image_enabled, yolo_ready=container.image_ready,
        ),
    )
