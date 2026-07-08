from __future__ import annotations

from enum import StrEnum


class FeedbackType(StrEnum):
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    REJECTED = "rejected"
    APPEAL_ACCEPTED = "appeal_accepted"
    APPEAL_REJECTED = "appeal_rejected"
