from __future__ import annotations

from enum import StrEnum


class ModerationAction(StrEnum):
    IGNORE = "IGNORE"
    LOG = "LOG"
    REVIEW = "REVIEW"
    WARN = "WARN"
    DELETE = "DELETE"
    DELETE_WARN = "DELETE_WARN"
    TIMEOUT = "TIMEOUT"
    BAN = "BAN"
