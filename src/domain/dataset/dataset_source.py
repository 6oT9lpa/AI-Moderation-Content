from __future__ import annotations

from enum import StrEnum


class DatasetSource(StrEnum):
    REAL_SAFE = "real_safe"
    REAL_MODERATED = "real_moderated"
    TEST_CHANNEL = "test_channel"
    MANUAL_SYNTHETIC = "manual_synthetic"
    PUBLIC_DATASET = "public_dataset"
    AI_GENERATED = "ai_generated"
