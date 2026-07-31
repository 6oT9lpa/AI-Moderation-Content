from pydantic import Field

from src.contracts.api.media_attachment_summary_schema import MediaAttachmentSummarySchema
from src.contracts.api.moderation_message_response_schema import ModerationMessageResponseSchema


class MediaModerationResponseSchema(ModerationMessageResponseSchema):
    attachments: tuple[MediaAttachmentSummarySchema, ...] = Field(default=(), max_length=10)

