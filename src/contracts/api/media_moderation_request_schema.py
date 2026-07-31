from pydantic import Field, model_validator

from src.contracts.api.api_model import ApiModel
from src.contracts.api.media_attachment_request_schema import MediaAttachmentRequestSchema
from src.contracts.api.moderation_message_request_schema import ModerationMessageRequestSchema


class MediaModerationRequestSchema(ApiModel):
    message: ModerationMessageRequestSchema
    attachments: tuple[MediaAttachmentRequestSchema, ...] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_attachment_identity(self) -> "MediaModerationRequestSchema":
        attachment_ids = tuple(attachment.attachment_id for attachment in self.attachments)
        if len(set(attachment_ids)) != len(attachment_ids):
            raise ValueError("attachment_id must be unique within the request")
        if not self.message.has_attachments:
            raise ValueError("message.has_attachments must be true")
        if self.message.attachment_count != len(self.attachments):
            raise ValueError("message.attachment_count must match attachments")
        return self

