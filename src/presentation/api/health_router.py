from datetime import datetime, timezone

from fastapi import APIRouter, Request

from src.contracts.api.health_response_schema import HealthResponseSchema
from src.presentation.api.dependencies import get_correlation_id

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponseSchema)
async def health(request: Request) -> HealthResponseSchema:
    host = request.client.host if request.client else ""
    if host not in {"127.0.0.1", "::1", "testclient"}:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="localhost_only")
    container = request.app.state.container
    if not container.database_ready:
        try:
            await container.database.connect()
            container.database_ready = True
        except Exception:
            container.database_ready = False
    rubert_ok = (
        not container.rubert_enabled
        or not container.rubert_required
        or container.rubert_ready
    )
    media_ok = not container.media_enabled or not container.media_required or container.media_ready
    ocr_ok = not container.ocr_enabled or not container.ocr_required or container.ocr_ready
    image_ok = not container.image_enabled or not container.image_required or container.image_ready
    ready = container.database_ready and container.policy_ready and rubert_ok and media_ok and ocr_ok and image_ok
    return HealthResponseSchema(
        status="ok" if ready else "degraded",
        database_status="ready" if container.database_ready else "unavailable",
        rubert_status="disabled" if not container.rubert_enabled else "ready" if container.rubert_ready else "unavailable",
        policy_status="ready" if container.policy_ready else "unavailable",
        media_ingestion_status="disabled" if not container.media_enabled else "ready" if container.media_ready else "unavailable",
        ocr_status="disabled" if not container.ocr_enabled else "ready" if container.ocr_ready else "unavailable",
        image_provider_status="disabled" if not container.image_enabled else "ready" if container.image_ready else "unavailable",
        policy_version=container.policy_version,
        model_id=container.model_id,
        ocr_model_id="paddleocr-ru-en" if container.ocr_ready else None,
        image_model_id=None,
        timestamp=datetime.now(timezone.utc),
        correlation_id=get_correlation_id(request),
    )
