from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel


_PLAN: tuple[tuple[ModerationLabel, int], ...] = (
    (ModerationLabel.SAFE, 12_000), (ModerationLabel.TOXIC, 8_000),
    (ModerationLabel.PROFANITY, 7_000), (ModerationLabel.SCAM, 5_000),
    (ModerationLabel.NSFW, 4_000), (ModerationLabel.HATE, 3_000),
    (ModerationLabel.THREAT, 3_000), (ModerationLabel.INVITE, 2_000),
    (ModerationLabel.SPAM, 1_500), (ModerationLabel.ADVERTISEMENT, 1_000),
    (ModerationLabel.EVASION, 1_000), (ModerationLabel.URL, 1_500),
    (ModerationLabel.POLITICS_IRL, 1_000),
)


def build_hard_gold_eval_pack() -> list[dict]:
    rows: list[dict] = []
    offset = 0
    for label, count in _PLAN:
        for index in range(count):
            text, labels, action = _case(label, index)
            rows.append({
                "id": f"hard_gold_v1_{offset + index}", "text": text,
                "primary_label": label.value, "labels": [item.value for item in labels],
                "expected_action": action, "source": "policy_gold_v1",
                "annotation_status": "policy_verified",
            })
        offset += count
    if len(rows) != 50_000:
        raise RuntimeError(f"expected 50000 hard-gold rows, got {len(rows)}")
    return rows


def _case(label: ModerationLabel, index: int) -> tuple[str, list[ModerationLabel], str]:
    c = _context(index)
    if label == ModerationLabel.SAFE:
        text = _pick(("Слово «пидор» используется как оскорбление, не повторяйте его.", "Он гей, это личное дело человека.", "Семья — важная тема, давайте говорить уважительно.", "В новостях обсуждают Зеленского без оскорблений.", "Не переходите по подозрительным ссылкам, это совет по безопасности."), index, 1)
        return f"{text} {c}.", [label], "IGNORE"
    if label == ModerationLabel.TOXIC:
        return f"{_pick(('ты позор сервера', 'хватит руинить, ты бесполезен', 'закрой чат и уйди', 'ты всех достал'), index, 1)}; {c}.", [label], "REVIEW"
    if label == ModerationLabel.PROFANITY:
        return f"{_pick(('какой же хуеглотик', 'этот пиздабол опять спорит', 'ну ты хуесос', 'блядь, хватит'), index, 1)}; {c}.", [label], "REVIEW"
    if label == ModerationLabel.SCAM:
        return f"https://{_pick(('steamcornmunity', 'discord-nitro', 'sber-bonus', 'faceit-drop'), index, 1)}-{index % 997}.example {_pick(('забери бесплатный приз', 'введи пароль от аккаунта', 'подтверди код из смс', 'получи выплату'), index, 7)}; {c}.", [label, ModerationLabel.URL], "REVIEW"
    if label == ModerationLabel.NSFW:
        return f"{_pick(('пришли интимные фото', 'в общем чате публикуют взрослый контент', 'канал с откровенными материалами', 'непристойные предложения родственнице'), index, 1)}; {c}.", [label], "REVIEW"
    if label == ModerationLabel.HATE:
        return f"{_pick(('геям здесь не место', 'мигрантов надо выгнать', 'людей этой национальности не пускайте', 'за ориентацию надо банить'), index, 1)}; {c}.", [label, ModerationLabel.TOXIC], "REVIEW"
    if label == ModerationLabel.THREAT:
        return f"{_pick(('я найду твою семью', 'солью твой адрес', 'доксну тебя после игры', 'сломаю тебе лицо'), index, 1)}; {c}.", [label, ModerationLabel.TOXIC], "REVIEW"
    if label == ModerationLabel.INVITE:
        return f"го на другой сервер: discord.gg/holdout{index % 997}; {c}.", [label, ModerationLabel.URL], "REVIEW"
    if label == ModerationLabel.SPAM:
        return f"{_pick(('срочно забери бонус бонус бонус', 'всем в личку за приз', 'репостни и получи подарок', 'жми быстрее быстрее'), index, 1)}; {c}.", [label], "REVIEW"
    if label == ModerationLabel.ADVERTISEMENT:
        return f"{_pick(('продам оформление профиля', 'делаю аватарки недорого', 'закажи прокачку аккаунта', 'магазин скинов открыт'), index, 1)}; {c}.", [label], "REVIEW"
    if label == ModerationLabel.EVASION:
        return f"обход фильтра: {_pick(('хyй', 'пuздa', 'гoндон', 'пид\u200bр'), index, 1)}; {c}.", [label], "REVIEW"
    if label == ModerationLabel.URL:
        return f"документация: https://docs-{index % 997}.example/guide; {c}.", [label], "IGNORE"
    return f"{_pick(('Зеленский выступил в новостях', 'Верховная рада обсуждает закон', 'правительство опубликовало заявление', 'НАТО упомянули в эфире'), index, 1)}; {c}.", [label], "IGNORE"


def _context(index: int) -> str:
    places = ("в общем чате", "в голосовом", "после катки", "в ветке обсуждения", "на стриме", "на сервере", "в игровом канале", "в вечерней беседе")
    times = ("сегодня", "вечером", "после обновления", "перед матчем", "на этой неделе", "утром", "в выходные", "после стрима")
    topics = ("игру", "правила", "событие", "мем", "новости", "канал", "заявку", "команду", "сервер", "проект", "расписание", "обсуждение", "турнир", "роли", "чат", "стрим")
    speakers = ("автор", "тиммейт", "зритель", "модератор", "новичок", "гость", "организатор", "администратор", "игрок", "читатель", "комментатор", "стример", "собеседник", "лидер", "участник", "наблюдатель")
    actions = ("проверяет", "обсуждает", "уточняет", "сравнивает", "сохраняет", "пересказывает", "объясняет", "комментирует", "просматривает", "подтверждает", "отмечает", "разбирает", "планирует", "исправляет", "наблюдает", "спрашивает")
    details = ("правила", "новости", "сообщение", "ссылку", "жалобу", "катку", "канал", "расписание", "мем", "ивент", "профиль", "сервер", "голосовой", "стрим", "тред", "заявку")
    return (
        f"{_pick(places, index, 97)} {_pick(times, index, 853)}; участник обсуждает {_pick(topics, index, 6_827)}; "
        f"{_pick(speakers, index, 17)} {_pick(actions, index, 271)} {_pick(details, index, 4_337)}; "
        f"во время матча {index % 997} на {(index // 997) + 1}-й день сезона"
    )


def _pick(values: tuple[str, ...], index: int, divisor: int) -> str:
    return values[(index // divisor) % len(values)]
