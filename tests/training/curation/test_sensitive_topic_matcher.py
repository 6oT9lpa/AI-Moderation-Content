import pytest

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.curation.sensitive_topic_matcher import SensitiveTopicMatcher


@pytest.mark.parametrize(
    ("text", "topic"),
    (
        ("Все чернокожие тупые", "race"),
        ("Women are inferior", "gender"),
        ("Я найду твою семью и убью", "family"),
    ),
)
def test_matcher_detects_targeted_harm(
    sensitive_topic_matcher: SensitiveTopicMatcher,
    text: str,
    topic: str,
) -> None:
    annotation = sensitive_topic_matcher.annotate(text)

    assert topic in annotation.topics
    assert ModerationLabel.TOXIC in annotation.labels


def test_racial_degradation_adds_hate(sensitive_topic_matcher: SensitiveTopicMatcher) -> None:
    annotation = sensitive_topic_matcher.annotate("Все чернокожие тупые и хуже животных")

    assert set(annotation.labels) >= {ModerationLabel.HATE, ModerationLabel.TOXIC}
    assert annotation.severity == 4


def test_gender_degradation_adds_hate(sensitive_topic_matcher: SensitiveTopicMatcher) -> None:
    annotation = sensitive_topic_matcher.annotate("Women are inferior and stupid")

    assert set(annotation.labels) >= {ModerationLabel.HATE, ModerationLabel.TOXIC}


def test_family_threat_adds_threat_without_hate(sensitive_topic_matcher: SensitiveTopicMatcher) -> None:
    annotation = sensitive_topic_matcher.annotate("Я найду твою семью и убью")

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
    sensitive_topic_matcher: SensitiveTopicMatcher,
    text: str,
) -> None:
    assert "family" in sensitive_topic_matcher.annotate(text).topics


@pytest.mark.parametrize(
    "text",
    (
        "Я приехал из родного города",
        "Перевод с родного языка",
    ),
)
def test_ambiguous_family_adjectives_are_not_detected(
    sensitive_topic_matcher: SensitiveTopicMatcher,
    text: str,
) -> None:
    assert "family" not in sensitive_topic_matcher.annotate(text).topics


def test_family_sexual_abuse_adds_nsfw(sensitive_topic_matcher: SensitiveTopicMatcher) -> None:
    annotation = sensitive_topic_matcher.annotate("Я изнасилую твоих родственников")

    assert set(annotation.labels) >= {
        ModerationLabel.NSFW,
        ModerationLabel.THREAT,
        ModerationLabel.TOXIC,
    }


def test_gender_sexual_context_is_not_automatically_toxic(
    sensitive_topic_matcher: SensitiveTopicMatcher,
) -> None:
    annotation = sensitive_topic_matcher.annotate("The woman discussed sex in an interview")

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
    sensitive_topic_matcher: SensitiveTopicMatcher,
    text: str,
) -> None:
    annotation = sensitive_topic_matcher.annotate(text)

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
    sensitive_topic_matcher: SensitiveTopicMatcher,
    text: str,
) -> None:
    annotation = sensitive_topic_matcher.annotate(text)

    assert annotation.labels == ()
