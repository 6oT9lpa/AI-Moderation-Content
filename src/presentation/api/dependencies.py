from fastapi import Header, HTTPException, Request, status

from src.application.api_moderation_service import ApiModerationService
from src.application.api_resource_unavailable_error import ApiResourceUnavailableError
from src.application.media_moderation_service import MediaModerationService
from src.application.effective_media_policy_resolver import EffectiveMediaPolicyResolver
from src.application.moderation_request_queue import ModerationRequestQueue


def get_api_service(request: Request) -> ApiModerationService:
    return request.app.state.container.service


def get_moderation_queue(request: Request) -> ModerationRequestQueue:
    return request.app.state.container.moderation_queue


def get_media_service(request: Request) -> MediaModerationService:
    service = request.app.state.container.media_service
    if service is None:
        raise ApiResourceUnavailableError("Media moderation is unavailable")
    return service


def get_correlation_id(request: Request) -> str:
    return request.state.correlation_id


def get_media_policy_resolver(request: Request) -> EffectiveMediaPolicyResolver:
    resolver = request.app.state.container.media_policy_resolver
    if resolver is None:
        raise ApiResourceUnavailableError("Media policy is unavailable")
    return resolver


async def require_internal_api_key(
    request: Request,
    internal_api_key: str | None = Header(default=None, alias="X-Internal-Api-Key"),
) -> None:
    if not request.app.state.container.key_validator.is_valid(internal_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_api_key")
