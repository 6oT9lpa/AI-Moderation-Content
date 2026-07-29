from __future__ import annotations

import hashlib

from src.training.curation.sensitive_topic_matcher import SensitiveTopicMatcher


class DatasetSplitAssigner:
    def __init__(self, *, validation_fraction: float = 0.1, seed: str = "sensitive-topics-v1") -> None:
        if not 0.0 < validation_fraction < 1.0:
            raise ValueError("validation_fraction must be between 0 and 1")
        self._validation_threshold = int(validation_fraction * 10_000)
        self._seed = seed

    def assign(self, text: str) -> str:
        normalized = SensitiveTopicMatcher.normalize_text(text)
        digest = hashlib.sha256(f"{self._seed}\0{normalized}".encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:8], "big") % 10_000
        return "validation" if bucket < self._validation_threshold else "train"
