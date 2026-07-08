from __future__ import annotations

from enum import StrEnum


class PolicyType(StrEnum):
    PREPROCESSING = "PREPROCESSING"
    MODERATION_RULE = "MODERATION_RULE"
    DECISION = "DECISION"
    ACTION = "ACTION"
