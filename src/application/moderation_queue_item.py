import asyncio

from dataclasses import dataclass

from src.contracts.api.moderation_message_request_schema import ModerationMessageRequestSchema
from src.contracts.api.moderation_message_response_schema import ModerationMessageResponseSchema


@dataclass(slots=True)
class ModerationQueueItem:
    request: ModerationMessageRequestSchema
    correlation_id: str
    future: asyncio.Future[ModerationMessageResponseSchema]
