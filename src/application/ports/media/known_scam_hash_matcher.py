from typing import Protocol

from src.domain.media.media_hashes import MediaHashes


class KnownScamHashMatcher(Protocol):
    def matches(self, hashes: MediaHashes) -> bool: ...
