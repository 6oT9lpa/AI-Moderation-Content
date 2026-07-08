from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DatasetTextSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_text: str | None
    normalized_text: str
    redacted_text: str
    model_text: str
    text_hash: str
    redactions: list[dict[str, Any]] = Field(default_factory=list)
    injection_markers: list[str] = Field(default_factory=list)
