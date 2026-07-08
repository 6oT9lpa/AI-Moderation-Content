from __future__ import annotations

from enum import StrEnum


class ActionExecutionStatus(StrEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    DRY_RUN = "DRY_RUN"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
