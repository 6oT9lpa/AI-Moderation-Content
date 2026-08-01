import json

import pytest
from pydantic import ValidationError

from src.domain.media.media_hashes import MediaHashes
from src.infrastructure.media.json_known_scam_hash_matcher import (
    JsonKnownScamHashMatcher,
)


def _hashes(*, sha256: str = "a" * 64, phash: str = "0000000000000000") -> MediaHashes:
    return MediaHashes(sha256=sha256, phash=phash, dhash="0" * 16, ahash="0" * 16)


def test_registry_matches_exact_sha_and_near_phash(tmp_path) -> None:
    registry = tmp_path / "known-scams.json"
    registry.write_text(
        json.dumps([{"sha256": "b" * 64}, {"phash": "0000000000000000"}]),
        encoding="utf-8",
    )
    matcher = JsonKnownScamHashMatcher.from_file(registry, max_phash_distance=2)

    assert matcher.matches(_hashes(sha256="b" * 64, phash="f" * 16))
    assert matcher.matches(_hashes(phash="0000000000000003"))
    assert not matcher.matches(_hashes(phash="000000000000000f"))


def test_registry_rejects_invalid_or_empty_entries(tmp_path) -> None:
    registry = tmp_path / "known-scams.json"
    registry.write_text('[{"phash":"not-a-hash"}]', encoding="utf-8")
    with pytest.raises(ValidationError):
        JsonKnownScamHashMatcher.from_file(registry)

    registry.write_text("[{}]", encoding="utf-8")
    with pytest.raises(ValueError, match="require"):
        JsonKnownScamHashMatcher.from_file(registry)
