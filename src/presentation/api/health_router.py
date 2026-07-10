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
    ready = container.database_ready and container.policy_ready
    return HealthResponseSchema(
        status="ok" if ready else "degraded",
        database_status="ready" if container.database_ready else "unavailable",
        rubert_status="ready" if container.rubert_ready else "unavailable",
        policy_status="ready" if container.policy_ready else "unavailable",
        policy_version=container.policy_version,
        model_id=container.model_id,
        timestamp=datetime.now(timezone.utc),
        correlation_id=get_correlation_id(request),
    )
