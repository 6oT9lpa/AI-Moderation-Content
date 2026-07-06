from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DatabaseCursorResult:
    rowcount: int
    lastrowid: Optional[int] = None
