from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_dataset_candidate import ModerationDatasetCandidate


def build_russian_slang_candidates() -> list[ModerationDatasetCandidate]:
    """Exactly 50k Russian chat-style examples with explicit provenance."""
    plan = (
        (25_000, ModerationLabel.SAFE),
        (10_000, ModerationLabel.TOXIC),
        (7_000, ModerationLabel.PROFANITY),
        (3_000, ModerationLabel.SPAM),
        (2_000, ModerationLabel.SCAM),
        (1_000, ModerationLabel.INVITE),
        (1_000, ModerationLabel.ADVERTISEMENT),
        (1_000, ModerationLabel.POLITICS_IRL),
    )
    rows: list[ModerationDatasetCandidate] = []
    offset = 0
    for count, label in plan:
        for index in range(count):
            text, labels = _text(label, index)
            rows.append(ModerationDatasetCandidate(
                text=text,
                labels=labels,
                primary_label=label,
                source_bucket="russian_slang",
                source_id=f"{label.value.lower()}_{offset + index}",
                severity=_severity(label),
                metadata={"generator": "russian_slang_v1", "style": "discord_chat"},
            ))
        offset += count
    return rows


def _text(label: ModerationLabel, index: int) -> tuple[str, list[ModerationLabel]]:
    nick = _pick(("бро", "чел", "дружище", "народ", "ребят", "тиммейт", "легенда", "чувак"), index, 1)
    context = _context(index)
    if label == ModerationLabel.SAFE:
        phrase = _pick(("жёстко сыграли", "имба катка", "норм вайб", "го ещё одну", "это люто", "кринжово, но смешно", "харош", "респект за помощь"), index, 11)
        return f"{nick}, {phrase}; {context}.", [label]
    if label == ModerationLabel.TOXIC:
        phrase = _pick(("ты реально кринж", "не душни", "ты токсик", "какой же ты нуб", "хватит руинить", "не позорь тим", "ты бесишь", "иди остынь"), index, 11)
        return f"{nick}, {phrase}; {context}.", [label]
    if label == ModerationLabel.PROFANITY:
        phrase = _pick(("ну ты хуеглот", "какой же пиздабол", "этот хуесосик опять тут", "бля, вот это фейл", "гондон, успокойся", "бездарт, читай правила", "ты ебанат", "хуеглотик в чате"), index, 11)
        return f"{nick}, {phrase}; {context}.", [label]
    if label == ModerationLabel.SPAM:
        return f"{nick}, {_pick(('залетай срочно за бонусом', 'всем плюс в личку за приз', 'не пропусти бесплатный дроп', 'репостни и получи подарок'), index, 7)}; {context}.", [label]
    if label == ModerationLabel.SCAM:
        return f"https://discord-nitro-{index % 997}.example {nick}, забери бесплатный nitro и {_pick(('введи пароль', 'подтверди код', 'авторизуйся сейчас', 'укажи карту'), index, 7)}; {context}.", [label, ModerationLabel.URL]
    if label == ModerationLabel.INVITE:
        return f"{nick}, го в новый сервер: discord.gg/slang{index % 997}; {context}.", [label]
    if label == ModerationLabel.ADVERTISEMENT:
        return f"{nick}, делаю {_pick(('аватарки', 'монтаж', 'оформление сервера', 'настройку бота'), index, 7)} недорого; {context}.", [label]
    return f"{nick}, {_pick(('Зеленский опять в новостях', 'Верховная рада обсуждает закон', 'президент выступил', 'НАТО упомянули в эфире'), index, 7)}; {context}.", [label]


def _context(index: int) -> str:
    rooms = ("в общем", "в войсе", "в оффтопе", "на стриме", "после катки", "в треде", "в лобби", "в пати")
    actions = ("обсуждаем обнову", "ждём ребят", "собираем сквад", "проверяем роли", "смотрим клип", "планируем матч", "болтаем вечером", "делимся мемами")
    moods = ("без агра", "по приколу", "без спешки", "в обычном чате", "по теме", "для всех", "с нормальным вайбом", "между делом")
    speakers = ("автор", "тиммейт", "зритель", "модер", "новичок", "гость", "друг", "игрок", "админ", "стример", "собеседник", "участник", "читатель", "организатор", "комментатор", "лидер")
    topics = ("катку", "обнову", "мем", "сервер", "роли", "ивент", "стрим", "матч", "канал", "пати", "чат", "правила", "команду", "новость", "заявку", "клип")
    return (
        f"{_pick(rooms, index, 97)} {_pick(actions, index, 853)}, {_pick(moods, index, 6_827)}; "
        f"{_pick(speakers, index, 17)} вспоминает {_pick(topics, index, 271)}"
    )


def _pick(values: tuple[str, ...], index: int, divisor: int) -> str:
    return values[(index // divisor) % len(values)]


def _severity(label: ModerationLabel) -> int:
    return {
        ModerationLabel.SAFE: 0, ModerationLabel.PROFANITY: 1, ModerationLabel.SPAM: 2,
        ModerationLabel.ADVERTISEMENT: 2, ModerationLabel.POLITICS_IRL: 2,
        ModerationLabel.INVITE: 3, ModerationLabel.TOXIC: 3, ModerationLabel.SCAM: 4,
    }[label]
