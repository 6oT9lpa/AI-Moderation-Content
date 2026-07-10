import asyncio

from src.application.api_moderation_service import ApiModerationService
from src.application.moderation_request_queue import ModerationRequestQueue
from src.infrastructure.api.internal_api_key_validator import InternalApiKeyValidator
from src.infrastructure.api.local_rate_limiter import LocalRateLimiter
from src.infrastructure.database.connection import DatabaseConnection


class ApiContainer:
    def __init__(
        self,
        service: ApiModerationService,
        database: DatabaseConnection,
        key_validator: InternalApiKeyValidator,
        rate_limiter: LocalRateLimiter,
        inference_semaphore: asyncio.Semaphore,
        moderation_queue: ModerationRequestQueue,
    ) -> None:
        self.service = service
        self.database = database
        self.key_validator = key_validator
        self.rate_limiter = rate_limiter
        self.inference_semaphore = inference_semaphore
        self.moderation_queue = moderation_queue
        self.database_ready = False
        self.rubert_ready = False
        self.rubert_enabled = True
        self.rubert_required = True
        self.policy_ready = False
        self.policy_version: str | None = None
        self.model_id: str | None = None
