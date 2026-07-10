from fastapi import APIRouter, Depends

from src.application.moderation_request_queue import ModerationRequestQueue
from src.contracts.api.moderation_message_request_schema import ModerationMessageRequestSchema
from src.contracts.api.moderation_message_response_schema import ModerationMessageResponseSchema
from src.presentation.api.dependencies import get_correlation_id, get_moderation_queue, require_internal_api_key

router = APIRouter(prefix="/moderation", tags=["moderation"], dependencies=[Depends(require_internal_api_key)])


@router.post("/messages", response_model=ModerationMessageResponseSchema)
async def moderate_message(
    payload: ModerationMessageRequestSchema,
    queue: ModerationRequestQueue = Depends(get_moderation_queue),
    correlation_id: str = Depends(get_correlation_id),
) -> ModerationMessageResponseSchema:
    return await queue.moderate(payload, correlation_id)
