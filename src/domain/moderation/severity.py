from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Severity:
    value: int

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 5:
            raise ValueError("severity must be between 0 and 5")
