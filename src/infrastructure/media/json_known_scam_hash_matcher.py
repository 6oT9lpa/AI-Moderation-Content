import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from src.domain.media.media_hashes import MediaHashes


class KnownScamHashEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    phash: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")


class JsonKnownScamHashMatcher:
    def __init__(
        self, entries: tuple[KnownScamHashEntry, ...], *, max_phash_distance: int = 6
    ) -> None:
        if not 0 <= max_phash_distance <= 64:
            raise ValueError("max_phash_distance must be between 0 and 64")
        if any(entry.sha256 is None and entry.phash is None for entry in entries):
            raise ValueError("known scam hash entries require sha256 or phash")
        self._sha256 = frozenset(entry.sha256 for entry in entries if entry.sha256)
        self._phashes = tuple(int(entry.phash, 16) for entry in entries if entry.phash)
        self._max_phash_distance = max_phash_distance

    @classmethod
    def from_file(
        cls, path: Path, *, max_phash_distance: int = 6
    ) -> "JsonKnownScamHashMatcher":
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = TypeAdapter(tuple[KnownScamHashEntry, ...]).validate_python(payload)
        return cls(entries, max_phash_distance=max_phash_distance)

    def matches(self, hashes: MediaHashes) -> bool:
        if hashes.sha256 in self._sha256:
            return True
        candidate = int(hashes.phash, 16)
        return any(
            (candidate ^ known).bit_count() <= self._max_phash_distance
            for known in self._phashes
        )
