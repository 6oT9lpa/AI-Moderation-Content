from src.modules.preprocessing.detectors.russian_profanity_detector import RussianProfanityDetector
from src.modules.preprocessing.rules.preprocessing_russian_profanity_policy import (
    PreprocessingRussianProfanityPolicy,
)


def test_russian_profanity_detector_uses_hash_map_for_obscene_and_literary_words() -> None:
    detector = RussianProfanityDetector(
        PreprocessingRussianProfanityPolicy(
            obscene_words=("хуе",),
            literary_words=("дурак",),
        ),
    )

    matches = detector.find_matches("Хуеглотик и дурак")

    assert matches == {"obscene": ("хуеглотик",), "literary": ("дурак",)}


def test_russian_profanity_detector_does_not_match_word_fragments() -> None:
    detector = RussianProfanityDetector(
        PreprocessingRussianProfanityPolicy(obscene_words=("хуй",)),
    )

    assert detector.find_matches("художественный") == {}


def test_russian_profanity_detector_matches_separator_obfuscation() -> None:
    detector = RussianProfanityDetector(
        PreprocessingRussianProfanityPolicy(
            obscene_words=("бля", "ебать", "сучка"),
            literary_words=("лох",),
        ),
    )

    assert detector.find_matches("б-л-я-д-с-т-в-о") == {"obscene": ("блядство",)}
    assert detector.find_matches("д о е б а т ь с я") == {"obscene": ("доебаться",)}
    assert detector.find_matches("с·у·ч·е·ч·к·а") == {"obscene": ("сучечка",)}
    assert detector.find_matches("л о  х") == {"literary": ("лох",)}


def test_russian_profanity_detector_does_not_flag_plain_letter_spelling_as_evasion() -> None:
    detector = RussianProfanityDetector(
        PreprocessingRussianProfanityPolicy(obscene_words=("бля",)),
    )

    assert detector.has_separator_obfuscation("а б в") is False
