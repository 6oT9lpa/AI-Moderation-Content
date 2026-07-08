from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class MessageFeatures:
    text_length: int
    token_count: int
    word_count: int
    line_count: int

    url_count: int
    invite_count: int
    mention_count: int
    role_mention_count: int
    channel_mention_count: int
    emoji_count: int
    emoji_ratio: float

    uppercase_ratio: float
    digit_ratio: float
    punctuation_count: int
    punctuation_ratio: float

    newline_count: int
    unique_chars: int
    spaces_count: int
    average_word_length: float
    longest_word_length: int

    repeated_char_score: float
    has_repeated_chars: bool
    duplicate_text_score: float
    recent_user_messages_10s: int
    recent_user_messages_60s: int
    recent_user_messages_10m: int
    repeated_messages_10m: int
    message_interval_seconds: float | None

    has_url: bool
    has_invite: bool
    has_shortener: bool
    has_zero_width: bool
    has_cyrillic: bool
    has_latin: bool
    has_mixed_scripts: bool
    has_suspicious_unicode: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "text_length": self.text_length,
            "token_count": self.token_count,
            "word_count": self.word_count,
            "line_count": self.line_count,
            "url_count": self.url_count,
            "invite_count": self.invite_count,
            "mention_count": self.mention_count,
            "role_mention_count": self.role_mention_count,
            "channel_mention_count": self.channel_mention_count,
            "emoji_count": self.emoji_count,
            "emoji_ratio": self.emoji_ratio,
            "uppercase_ratio": self.uppercase_ratio,
            "digit_ratio": self.digit_ratio,
            "punctuation_count": self.punctuation_count,
            "punctuation_ratio": self.punctuation_ratio,
            "newline_count": self.newline_count,
            "unique_chars": self.unique_chars,
            "spaces_count": self.spaces_count,
            "average_word_length": self.average_word_length,
            "longest_word_length": self.longest_word_length,
            "repeated_char_score": self.repeated_char_score,
            "has_repeated_chars": self.has_repeated_chars,
            "duplicate_text_score": self.duplicate_text_score,
            "recent_user_messages_10s": self.recent_user_messages_10s,
            "recent_user_messages_60s": self.recent_user_messages_60s,
            "recent_user_messages_10m": self.recent_user_messages_10m,
            "repeated_messages_10m": self.repeated_messages_10m,
            "message_interval_seconds": self.message_interval_seconds,
            "has_url": self.has_url,
            "has_invite": self.has_invite,
            "has_shortener": self.has_shortener,
            "has_zero_width": self.has_zero_width,
            "has_cyrillic": self.has_cyrillic,
            "has_latin": self.has_latin,
            "has_mixed_scripts": self.has_mixed_scripts,
            "has_suspicious_unicode": self.has_suspicious_unicode,
        }
