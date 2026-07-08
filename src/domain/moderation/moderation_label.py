from __future__ import annotations

from enum import StrEnum


class ModerationLabel(StrEnum):
    SAFE = "SAFE"
    SPAM = "SPAM"
    ADVERTISEMENT = "ADVERTISEMENT"
    INVITE = "INVITE"
    SCAM = "SCAM"
    TOXIC = "TOXIC"
    HATE = "HATE"
    THREAT = "THREAT"
    NSFW = "NSFW"
    EVASION = "EVASION"
    FLOOD = "FLOOD"
    URL = "URL"
    IMAGE_SCAM = "IMAGE_SCAM"
