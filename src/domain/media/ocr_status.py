from __future__ import annotations

from enum import StrEnum


class OcrStatus(StrEnum):
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
