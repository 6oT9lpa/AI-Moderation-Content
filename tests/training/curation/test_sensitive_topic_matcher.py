from pathlib import Path

import pytest

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.curation.sensitive_topic_matcher import SensitiveTopicMatcher


CONFIG_PATH = Path("configs/training/sensitive_topic_curation.yaml")


@pytest.fixture(scope="module")
def matcher() -> SensitiveTopicMatcher:
    return SensitiveTopicMatcher.from_yaml(CONFIG_PATH)


@pytest.mark.parametrize(
    ("text", "topic"),
    (
        ("Все чернокожие тупые", "race"),
        ("Women are inferior", "gender"),
        ("Я найду твою семью и убью", "family"),
    ),
)
def test_matcher_detects_targeted_harm(
    matcher: SensitiveTopicMatcher,
    text: str,
    topic: str,
) -> None:
    annotation = matcher.annotate(text)

    assert topic in annotation.topics
    assert ModerationLabel.TOXIC in annotation.labels


def test_racial_degradation_adds_hate(matcher: SensitiveTopicMatcher) -> None:
    annotation = matcher.annotate("Все чернокожие тупые и хуже животных")

    assert set(annotation.labels) >= {ModerationLabel.HATE, ModerationLabel.TOXIC}
    assert annotation.severity == 4


def test_gender_degradation_adds_hate(matcher: SensitiveTopicMatcher) -> None:
    annotation = matcher.annotate("Women are inferior and stupid")

    assert set(annotation.labels) >= {ModerationLabel.HATE, ModerationLabel.TOXIC}


def test_family_threat_adds_threat_without_hate(matcher: SensitiveTopicMatcher) -> None:
    annotation = matcher.annotate("Я найду твою семью и убью")

    assert set(annotation.labels) >= {ModerationLabel.THREAT, ModerationLabel.TOXIC}
    assert ModerationLabel.HATE not in annotation.labels
    assert annotation.severity == 5


@pytest.mark.parametrize(
    "text",
    (
        "Я убью всю твою родню",
        "Я найду твоих родных",
    ),
)
def test_family_inflections_are_detected(
    matcher: SensitiveTopicMatcher,
    text: str,
) -> None:
    assert "family" in matcher.annotate(text).topics


@pytest.mark.parametrize(
    "text",
    (
        "Я приехал из родного города",
        "Перевод с родного языка",
    ),
)
def test_ambiguous_family_adjectives_are_not_detected(
    matcher: SensitiveTopicMatcher,
    text: str,
) -> None:
    assert "family" not in matcher.annotate(text).topics


def test_family_sexual_abuse_adds_nsfw(matcher: SensitiveTopicMatcher) -> None:
    annotation = matcher.annotate("Я изнасилую твоих родственников")

    assert set(annotation.labels) >= {
        ModerationLabel.NSFW,
        ModerationLabel.THREAT,
        ModerationLabel.TOXIC,
    }


def test_gender_sexual_context_is_not_automatically_toxic(
    matcher: SensitiveTopicMatcher,
) -> None:
    annotation = matcher.annotate("The woman discussed sex in an interview")

    assert annotation.labels == (ModerationLabel.NSFW,)


@pytest.mark.parametrize(
    "text",
    (
        "Моя семья приехала в гости",
        "Мужчины и женщины имеют равные права",
        "Я купил белые кроссовки",
        "Расизм против чернокожих недопустим",
    ),
)
def test_matcher_does_not_autolabel_neutral_or_counter_context(
    matcher: SensitiveTopicMatcher,
    text: str,
) -> None:
    annotation = matcher.annotate(text)

    assert annotation.labels == ()


@pytest.mark.parametrize(
    "text",
    (
        (
            "почему люди особенно преклонного возраста любят брать себе в дом "
            "животных, с которыми не так чувствуют себя одинокими дети выросли"
        ),
        (
            "усиным пером, с затейливыми завитушками. двести лет числил за собой "
            "именитый купеческий род ратчиных, раньше держали соляные откупа, "
            "торговали мукою и гуртами, – двести лет (прадед, дед, отец, сын, "
            "внук, правнук) на одном месте, в соляных рядах (теперь уничтожены)"
        ),
        (
            "если я выясню, что гузман имел к этому какое-то отношение, то я убью "
            "этого любителя, мужик, голыми руками"
        ),
    ),
)
def test_matcher_does_not_bind_distant_harm_to_sensitive_topic(
    matcher: SensitiveTopicMatcher,
    text: str,
) -> None:
    annotation = matcher.annotate(text)

    assert annotation.labels == ()
