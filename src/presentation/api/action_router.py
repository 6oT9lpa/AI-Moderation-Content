from fastapi import APIRouter, Depends

from src.application.api_moderation_service import ApiModerationService
from src.contracts.api.action_result_request_schema import ActionResultRequestSchema
from src.contracts.api.api_ack_schema import ApiAckSchema
from src.presentation.api.dependencies import get_api_service, get_correlation_id, require_internal_api_key

router = APIRouter(prefix="/actions", tags=["actions"], dependencies=[Depends(require_internal_api_key)])


@router.post("/result", response_model=ApiAckSchema)
async def submit_action_result(
    payload: ActionResultRequestSchema,
    service: ApiModerationService = Depends(get_api_service),
    correlation_id: str = Depends(get_correlation_id),
) -> ApiAckSchema:
    return await service.submit_action_result(payload, correlation_id)
