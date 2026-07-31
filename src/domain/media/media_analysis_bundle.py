from pydantic import BaseModel, ConfigDict, Field

from src.domain.media.media_attachment_analysis import MediaAttachmentAnalysis


class MediaAnalysisBundle(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attachments: tuple[MediaAttachmentAnalysis, ...] = Field(default=(), max_length=10)

