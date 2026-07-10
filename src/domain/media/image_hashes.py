from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ImageHashes:
    sha256: str | None = None
    phash: str | None = None
    dhash: str | None = None
    ahash: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "sha256": self.sha256,
            "phash": self.phash,
            "dhash": self.dhash,
            "ahash": self.ahash,
        }
