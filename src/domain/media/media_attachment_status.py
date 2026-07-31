from enum import StrEnum


class MediaAttachmentStatus(StrEnum):
    ANALYZED = "analyzed"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    UNAVAILABLE = "unavailable"

