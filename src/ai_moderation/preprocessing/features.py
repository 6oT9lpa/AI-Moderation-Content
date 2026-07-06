from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Ratio = Annotated[float, Field(ge=0.0, le=1.0)]


class MessageFeatures(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    message_length: int = Field(ge=0)
    words_count: int = Field(ge=0)

    emoji_count: int = Field(ge=0)

    mentions_count: int = Field(ge=0)
    role_mentions_count: int = Field(ge=0)

    caps_ratio: Ratio = 0.0
    digits_ratio: Ratio = 0.0

    repeated_chars: bool = False

    punctuation_count: int = Field(ge=0)
    punctuation_ratio: Ratio = 0.0

    newline_count: int = Field(ge=0)

    unique_chars: int = Field(ge=0)

    spaces_count: int = Field(ge=0)

    average_word_length: float = Field(ge=0.0)

    longest_word: int = Field(ge=0)

    has_cyrillic: bool = False
    has_latin: bool = False
    mixed_alphabet: bool = False