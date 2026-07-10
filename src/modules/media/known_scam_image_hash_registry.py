from __future__ import annotations

from src.domain.media.image_hashes import ImageHashes
from src.domain.media.known_scam_image_hash import KnownScamImageHash
from src.domain.media.known_scam_image_match import KnownScamImageMatch
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class KnownScamImageHashRegistry:
    def __init__(self, records: tuple[KnownScamImageHash, ...] = (), *, max_distance: int = 6) -> None:
        if not 0 <= max_distance <= 64:
            raise ValueError("max_distance must be between 0 and 64")
        self._records = records
        self._max_distance = max_distance
        logger.info("Known scam image hash registry initialized records=%s max_distance=%s", len(records), max_distance)

    def find_match(self, hashes: ImageHashes) -> KnownScamImageMatch | None:
        candidates: list[KnownScamImageMatch] = []
        for record in self._records:
            for hash_type in ("phash", "dhash", "ahash"):
                candidate_hash = getattr(hashes, hash_type)
                known_hash = getattr(record, hash_type)
                if candidate_hash is None or known_hash is None or len(candidate_hash) != len(known_hash):
                    continue
                distance = self._hamming_distance(candidate_hash, known_hash)
                if distance <= self._max_distance:
                    candidates.append(
                        KnownScamImageMatch(record.record_id, hash_type, distance, record.scam_subtype)
                    )
        if not candidates:
            logger.debug("Known scam image hash not found")
            return None
        match = min(candidates, key=lambda item: item.distance)
        logger.warning("Known scam image hash matched record_id=%s hash_type=%s distance=%s", match.record_id, match.hash_type, match.distance)
        return match

    def _hamming_distance(self, first: str, second: str) -> int:
        return (int(first, 16) ^ int(second, 16)).bit_count()
