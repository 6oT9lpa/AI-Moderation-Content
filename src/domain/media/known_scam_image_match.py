from __future__ import annotations

from dataclasses import dataclass

from src.domain.moderation.scam_subtype import ScamSubtype


@dataclass(slots=True, frozen=True)
class KnownScamImageMatch:
    record_id: str
    hash_type: str
    distance: int
    scam_subtype: ScamSubtype | None

    def to_dict(self) -> dict[str, str | int | None]:
        return {
            "record_id": self.record_id,
            "hash_type": self.hash_type,
            "distance": self.distance,
            "scam_subtype": self.scam_subtype.value if self.scam_subtype else None,
        }
