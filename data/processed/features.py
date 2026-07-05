from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class MessageFeatures:

    message_length: int
    words_count: int

    emoji_count: int

    mentions_count: int
    role_mentions_count: int

    caps_ratio: float
    digits_ratio: float

    repeated_chars: bool

    punctuation_count: int
    punctuation_ratio: float

    newline_count: int

    unique_chars: int

    spaces_count: int

    average_word_length: float

    longest_word: int

    has_cyrillic: bool
    has_latin: bool
    mixed_alphabet: bool