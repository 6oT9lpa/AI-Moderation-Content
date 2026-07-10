from __future__ import annotations

from src.contracts.message_preprocess_input_schema import MessagePreprocessInputSchema
from src.domain.message_context import MessageContext
from src.infrastructure.logging import get_logger
from src.modules.preprocessing.text_preprocessor import TextPreprocessor

logger = get_logger("tests.media")


class CapturingTextPreprocessor:
    def __init__(self, delegate: TextPreprocessor | None = None) -> None:
        self._delegate = delegate or TextPreprocessor()
        self.last_payload: MessagePreprocessInputSchema | None = None

    async def process(self, payload: MessagePreprocessInputSchema) -> MessageContext:
        self.last_payload = payload
        logger.info(
            "Capturing preprocessor received message_id=%s has_attachments=%s attachment_count=%s",
            payload.message_id,
            payload.has_attachments,
            payload.attachment_count,
        )
        return await self._delegate.process(payload)
