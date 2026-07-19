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
