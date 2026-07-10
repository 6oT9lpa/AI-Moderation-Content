from fastapi import APIRouter, Depends

from src.application.api_moderation_service import ApiModerationService
from src.contracts.api.api_ack_schema import ApiAckSchema
from src.contracts.api.moderation_feedback_request_schema import ModerationFeedbackRequestSchema
from src.presentation.api.dependencies import get_api_service, get_correlation_id, require_internal_api_key

router = APIRouter(prefix="/moderation", tags=["moderation"], dependencies=[Depends(require_internal_api_key)])


@router.post("/feedback", response_model=ApiAckSchema)
async def submit_feedback(
    payload: ModerationFeedbackRequestSchema,
    service: ApiModerationService = Depends(get_api_service),
    correlation_id: str = Depends(get_correlation_id),
) -> ApiAckSchema:
    return await service.submit_feedback(payload, correlation_id)
