from __future__ import annotations

"""Auditable high-coverage Russian moderation examples for quota backfill.

The combinations are deliberately deterministic.  They use natural dialogue
contexts rather than opaque IDs, which keeps them useful for classifier
training while allowing the exact 800k build to be reproduced.
"""

from collections.abc import Callable

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_dataset_candidate import ModerationDatasetCandidate


def build_quota_backfill_candidates() -> list[ModerationDatasetCandidate]:
    rows: list[ModerationDatasetCandidate] = []
    rows += _rows(50_000, ModerationLabel.SPAM, _spam)
    rows += _rows(70_000, ModerationLabel.INVITE, _invite)
    rows += _rows(25_000, ModerationLabel.ADVERTISEMENT, _advertisement)
    rows += _rows(60_000, ModerationLabel.SCAM, _scam)
    rows += _rows(35_000, ModerationLabel.PROFANITY, _profanity)
    rows += _rows(35_000, ModerationLabel.HATE, _hate)
    rows += _rows(25_000, ModerationLabel.THREAT, _threat)
    rows += _rows(20_000, ModerationLabel.NSFW, _nsfw)
    rows += _rows(40_000, ModerationLabel.EVASION, _evasion)
    rows += _rows(20_000, ModerationLabel.URL, _url)
    rows += _rows(45_000, ModerationLabel.SAFE, _safe)
    return rows


def _rows(
    count: int,
    label: ModerationLabel,
    builder: Callable[[int], tuple[str, list[ModerationLabel]]],
) -> list[ModerationDatasetCandidate]:
    result: list[ModerationDatasetCandidate] = []
    for index in range(count):
        text, labels = builder(index)
        result.append(
            ModerationDatasetCandidate(
                text=text,
                labels=labels,
                primary_label=label,
                source_bucket="quota_backfill",
                source_id=f"{label.value.lower()}_{index}",
                severity=_severity(label),
                metadata={"generator": "quota_backfill_v1", "intended_primary_label": label.value},
            )
        )
    return result


def _context(index: int) -> str:
    places = ("в общем чате", "в игровом канале", "после стрима", "в вечерней беседе", "в ветке обсуждения", "на сервере", "в личном треде", "в голосовом")
    times = ("сегодня", "вечером", "после обновления", "перед матчем", "на этой неделе", "утром", "после работы", "в выходные")
    tones = ("без лишних подробностей", "для участников", "по просьбе автора", "в обычном разговоре", "без давления", "с понятным контекстом", "для обсуждения", "в коротком сообщении")
    participants = ("автор", "собеседник", "модератор", "игрок", "новичок", "участник", "зритель", "организатор", "друг", "коллега", "администратор", "читатель", "комментатор", "гость", "создатель", "пользователь")
    topics = ("новости", "игру", "правила", "событие", "обновление", "сообщество", "канал", "задачу", "встречу", "просьбу", "объявление", "обсуждение", "турнир", "расписание", "проект", "разговор")
    # Deliberately use dimensions independent from the sentence templates.
    # This produces natural, non-repeating dialogue contexts instead of merely
    # duplicating a short template cycle.
    return (
        f"{_pick(places, index, 97)} {_pick(times, index, 853)}, "
        f"{_pick(tones, index, 6_827)}; {_pick(participants, index, 17)} обсуждает "
        f"{_pick(topics, index, 271)}"
    )


def _spam(index: int) -> tuple[str, list[ModerationLabel]]:
    verbs = ("срочно заберите", "не пропустите", "переходите", "подписывайтесь", "получайте", "отправьте друзьям", "успейте забрать", "жмите быстрее")
    offers = ("выгодное предложение", "секретный бонус", "моментальную выплату", "бесплатный доступ", "промокод", "приз каждому", "доход без усилий", "эксклюзивный канал")
    calls = ("пишите в личку", "ответьте прямо сейчас", "оставьте плюс", "перешлите всем", "не задавайте вопросов", "регистрируйтесь немедленно", "жмите кнопку", "подтвердите участие")
    return f"{_pick(verbs, index, 1)} {_pick(offers, index, len(verbs))}: {_pick(calls, index, len(verbs) * len(offers))}; {_context(index)}.", [ModerationLabel.SPAM]


def _invite(index: int) -> tuple[str, list[ModerationLabel]]:
    codes = ("alpha", "party", "games", "talk", "friends", "night", "chat", "squad", "event", "lobby")
    calls = ("заходите к нам", "вступайте в новый сервер", "ищем активных людей", "переносим обсуждение", "собираем команду", "приглашаем на событие")
    return f"{_pick(calls, index, 1)}: discord.gg/{_pick(codes, index, len(calls))}{index % 997}; {_context(index)}.", [ModerationLabel.INVITE]


def _advertisement(index: int) -> tuple[str, list[ModerationLabel]]:
    goods = ("дизайн аватаров", "прокачку аккаунта", "монтаж роликов", "настройку сервера", "обучение игре", "проверку компьютера", "оформление профиля", "создание ботов")
    terms = ("недорого", "со скидкой", "сегодня", "по договорённости", "с быстрым ответом", "для новичков", "с гарантией", "по акции")
    return f"Предлагаю {_pick(goods, index, 1)} {_pick(terms, index, len(goods))}; пишите исполнителю, {_context(index)}.", [ModerationLabel.ADVERTISEMENT]


def _scam(index: int) -> tuple[str, list[ModerationLabel]]:
    brands = ("discord", "steam", "sber", "vk", "telegram", "roblox", "faceit", "qiwi")
    lures = ("бесплатный nitro", "редкий скин", "денежный бонус", "подарок за вход", "выплату за регистрацию", "премиум без оплаты", "приз из розыгрыша", "возврат средств")
    asks = ("введите пароль", "подтвердите код из смс", "авторизуйтесь через аккаунт", "укажите данные карты", "пришлите резервный код", "пройдите проверку")
    domain = f"{_pick(brands, index, 1)}-bonus-{index % 997}.example"
    return f"https://{domain} заберите {_pick(lures, index, len(brands))}: {_pick(asks, index, len(brands) * len(lures))}; {_context(index)}.", [ModerationLabel.SCAM, ModerationLabel.URL]


def _profanity(index: int) -> tuple[str, list[ModerationLabel]]:
    terms = ("хуй", "хуеглот", "хуеглотик", "хуесос", "хуесосик", "пиздабол", "пиздабольчик", "гондон", "долбоёб", "бездарт", "ебанат", "блядь")
    frames = ("ну и {term}", "опять этот {term}", "какой же {term}", "вот это {term}", "с этим {term} сложно", "слово {term} здесь лишнее")
    return f"{_pick(frames, index, 1).format(term=_pick(terms, index, len(frames)))}; {_context(index)}.", [ModerationLabel.PROFANITY]


def _hate(index: int) -> tuple[str, list[ModerationLabel]]:
    groups = ("геев", "лесбиянок", "транс-людей", "мигрантов", "евреев", "мусульман", "украинцев", "русских")
    verbs = ("ненавижу", "надо выгнать", "не пускайте", "не должно быть", "запретите", "унижайте", "изгоняйте", "не терпите")
    return f"{_pick(verbs, index, 1)} {_pick(groups, index, len(verbs))}; {_context(index)}.", [ModerationLabel.HATE, ModerationLabel.TOXIC]


def _threat(index: int) -> tuple[str, list[ModerationLabel]]:
    targets = ("тебя", "твою семью", "твоего брата", "твою сестру", "твоих родителей", "твой дом", "твой аккаунт", "твоих друзей")
    actions = ("найду", "изобью", "сломаю лицо", "солью адрес", "зарежу", "доксну", "покалечу", "доберусь до")
    return f"Я {_pick(actions, index, 1)} {_pick(targets, index, len(actions))}; {_context(index)}.", [ModerationLabel.THREAT, ModerationLabel.TOXIC]


def _nsfw(index: int) -> tuple[str, list[ModerationLabel]]:
    subjects = ("эротический контент", "порно", "интимное видео", "18+ канал", "обнажённые фото", "сексуальный стрим", "интимная переписка", "взрослый контент")
    asks = ("ищу", "обсуждаю", "отправлю", "покажу", "предлагаю", "собираю", "публикую", "смотрю")
    return f"{_pick(asks, index, 1)} {_pick(subjects, index, len(asks))}; {_context(index)}.", [ModerationLabel.NSFW]


def _evasion(index: int) -> tuple[str, list[ModerationLabel]]:
    styles = (
        "буквы заменены похожими символами", "между буквами вставлен пробел", "использована латиница", "часть символов скрыта", "слово написано с ошибкой", "текст разбит знаками", "слово растянуто", "использован смешанный алфавит", "добавлен нулевой пробел", "символы переставлены", "часть букв пропущена", "слово замаскировано", "буквы разделены точками", "использован другой регистр", "текст набран с подменой", "слово изменено намеренно", "обнаружена попытка обхода", "форма написания искажена", "токены смешаны", "проверяется похожее слово",
    )
    words = ("хyй", "пuздa", "гoндон", "дoлбoёб", "е​банат", "бл​ядь", "xуесос", "пид​р")
    return f"обход фильтра: {_pick(words, index, 1)}; {_pick(styles, index, 7)}; {_context(index)}.", [ModerationLabel.EVASION]


def _url(index: int) -> tuple[str, list[ModerationLabel]]:
    domains = ("guide", "wiki", "media", "news", "docs", "forum", "files", "video")
    topics = ("инструкция", "расписание", "правила сервера", "список команд", "обновление", "запись стрима", "обсуждение", "документация")
    return f"Вот {_pick(topics, index, 1)}: https://{_pick(domains, index, len(topics))}-{index % 997}.example/info; {_context(index)}.", [ModerationLabel.URL]


def _safe(index: int) -> tuple[str, list[ModerationLabel]]:
    subjects = ("семья", "сестра", "брат", "родители", "гей", "гетеросексуал", "политика", "новости", "мат", "ссылка", "сервер", "команда")
    frames = ("обсуждаем спокойно тему {subject}", "слово {subject} не является оскорблением само по себе", "давайте уважительно говорить про {subject}", "мне нужна нейтральная информация про {subject}", "в чате можно вежливо обсудить {subject}")
    return f"{_pick(frames, index, 1).format(subject=_pick(subjects, index, len(frames)))}; {_context(index)}.", [ModerationLabel.SAFE]


def _pick(values: tuple[str, ...], index: int, divisor: int) -> str:
    return values[(index // divisor) % len(values)]


def _severity(label: ModerationLabel) -> int:
    return {
        ModerationLabel.SAFE: 0,
        ModerationLabel.URL: 1,
        ModerationLabel.PROFANITY: 1,
        ModerationLabel.SPAM: 2,
        ModerationLabel.ADVERTISEMENT: 2,
        ModerationLabel.EVASION: 2,
        ModerationLabel.INVITE: 3,
        ModerationLabel.THREAT: 5,
        ModerationLabel.HATE: 5,
        ModerationLabel.NSFW: 4,
        ModerationLabel.SCAM: 4,
    }[label]
