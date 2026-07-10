from __future__ import annotations

import re
from dataclasses import dataclass

from src.domain.moderation.scam_subtype import ScamSubtype


@dataclass(slots=True, frozen=True)
class KnownScamImageHash:
    HASH_RE = re.compile(r"[0-9a-f]{16}", re.IGNORECASE)

    record_id: str
    phash: str | None = None
    dhash: str | None = None
    ahash: str | None = None
    scam_subtype: ScamSubtype | None = None

    def __post_init__(self) -> None:
        hashes = (self.phash, self.dhash, self.ahash)
        if not isinstance(self.record_id, str) or not self.record_id.strip():
            raise ValueError("record_id is required")
        if not any(hashes):
            raise ValueError("at least one perceptual hash is required")
        if any(
            value is not None and (not isinstance(value, str) or not self.HASH_RE.fullmatch(value))
            for value in hashes
        ):
            raise ValueError("perceptual hashes must contain exactly 16 hexadecimal characters")
