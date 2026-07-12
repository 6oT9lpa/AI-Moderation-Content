from __future__ import annotations

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_dataset_candidate import ModerationDatasetCandidate


def build_russian_robustness_candidates() -> list[ModerationDatasetCandidate]:
    """Deterministic, auditable Russian edge cases for the long-tail classes.

    These are deliberately templates rather than LLM-generated text: every item has
    a known label and can be regenerated identically during dataset audits.
    """
    candidates: list[ModerationDatasetCandidate] = []
    candidates.extend(_profanity_cases(72_000))
    candidates.extend(_politics_cases(64_000))
    candidates.extend(_family_and_identity_cases(24_000))
    candidates.extend(_scam_context_cases(20_000))
    candidates.extend(_discord_mention_context_cases(12_000))
    return candidates


def _discord_mention_context_cases(count: int) -> list[ModerationDatasetCandidate]:
    """Contrast real Discord mention syntax with targeted abusive messages.

    IDs are intentionally synthetic.  The sanitizer replaces them with the
    canonical mention token, so the model learns that a mention is context, not
    a URL or spam marker.
    """
    safe_frames = (
        "<@{user}> посмотри, пожалуйста, обновление в канале.",
        "<@{user}> ты сегодня будешь в голосовом?",
        "<@{user}> <@{user2}> давайте соберёмся вечером.",
        "<@{user}> спасибо за помощь с каткой!",
    )
    toxic_frames = (
        "<@{user}> ты пидр.",
        "<@{user}> хватит вести себя как хуеглот.",
        "<@{user}> <@{user2}> <@{user3}> вы все достали, пидоры.",
        "<@{user}> <@{user2}> <@{user3}> прекратите, долбоёбы.",
    )
    rows: list[ModerationDatasetCandidate] = []
    for index in range(count):
        user = 10_000_000_000_000_000 + index
        values = {"user": user, "user2": user + 1, "user3": user + 2}
        if index % 2:
            text = _select(toxic_frames, index // 2).format(**values)
            labels = [ModerationLabel.TOXIC, ModerationLabel.PROFANITY]
            primary_label = ModerationLabel.TOXIC
        else:
            text = _select(safe_frames, index // 2).format(**values)
            labels = [ModerationLabel.SAFE]
            primary_label = ModerationLabel.SAFE
        rows.append(_candidate("russian_robustness", 400_000 + index, primary_label, text, labels))
    return rows


def _profanity_cases(count: int) -> list[ModerationDatasetCandidate]:
    variants = (
        "хуй", "хуеглот", "хуеглотик", "хуесос", "хуесосик", "пиздабол",
        "пиздабольчик", "гондон", "долбоеб", "бездарь", "бездарт", "ебанат",
    )
    frames = (
        "ну ты {term}", "слышь, {term}", "в чате опять {term}",
        "какой же ты {term}", "не веди себя как {term}", "ты просто {term}",
    )
    bare_frames = (
        "ну и {term}", "опять это {term}", "{term}, вот же ситуация",
        "вот это {term}", "какой {term} сегодня", "с этим {term} всё сложно",
    )
    contexts = (
        "после такой катки", "и не спорь", "выйди из голосового", "весь сервер устал",
        "это уже не смешно", "зачем ты снова пишешь", "учись играть", "не позорь команду",
    )
    forms = ("{frame}", "{frame}, {context}", "{context}: {frame}")
    qualifiers = (
        "серьёзно", "без шуток", "опять", "просто", "реально", "честно", "наконец-то",
        "в который раз", "как обычно", "после обновления", "в этой игре", "сегодня",
        "в голосовом", "в общем чате", "на стриме", "в нашей пати",
    )
    audiences = (
        "и все это видят", "команда уже устала", "никто не спорит", "модераторы предупреждали",
        "не превращай чат в помойку", "остальные хотят спокойно играть", "это мешает всем",
        "чат не обязан это терпеть", "тебя уже просили остановиться", "тема закрыта",
        "не продолжай", "сделай выводы", "потом не жалуйся", "мы это обсудили",
        "не провоцируй других", "выйди на паузу",
    )
    rows: list[ModerationDatasetCandidate] = []
    for index in range(count):
        term = _choice(variants, index, 1)
        targeted = index % 6 == 0
        frame_options = frames if targeted else bare_frames
        frame = _choice(frame_options, index, len(variants)).format(term=term)
        text = _choice(forms, index, len(variants) * len(frames)).format(
            frame=frame,
            context=_choice(contexts, index, len(variants) * len(frames) * len(forms)),
        )
        text = f"{_choice(qualifiers, index, 1_728)}: {text}; {_choice(audiences, index, 27_648)}."
        primary_label = ModerationLabel.TOXIC if targeted else ModerationLabel.PROFANITY
        labels = [ModerationLabel.TOXIC, ModerationLabel.PROFANITY] if targeted else [ModerationLabel.PROFANITY]
        rows.append(_candidate("russian_robustness", index, primary_label, text, labels))
    return rows


def _politics_cases(count: int) -> list[ModerationDatasetCandidate]:
    subjects = (
        "Зеленский", "Верховная рада", "Госдума", "Кремль", "президент США",
        "правительство России", "правительство Украины", "НАТО", "Белый дом", "парламент Беларуси",
    )
    judgments = (
        "ведут себя как идиоты", "совсем оторвались от людей", "позорят страну",
        "приняли бездарное решение", "не заслуживают доверия", "развели очередной скандал",
        "опять устроили цирк", "должны объяснить это решение",
    )
    frames = (
        "{subject} {judgment}", "по-моему, {subject} {judgment}",
        "обсуждаем, почему {subject} {judgment}", "в новостях: {subject} {judgment}",
    )
    suffixes = ("", " в этом месяце", " на глазах у всех", " — вот и вся политика", " в очередной раз")
    contexts = (
        "после заседания", "в прямом эфире", "в новостной ленте", "на международной встрече",
        "после выборов", "во время обсуждения бюджета", "на фоне скандала", "в парламентской дискуссии",
        "в интервью", "на пресс-конференции", "в комментариях к новости", "после голосования",
        "в дипломатическом споре", "на форуме", "в утреннем выпуске", "в аналитическом обзоре",
    )
    audiences = (
        "это обсуждают зрители", "в чате спорят участники", "редакция собирает мнения",
        "комментарии разделились", "аналитики дают оценки", "люди ждут ответа",
        "тема остаётся спорной", "обсуждение продолжается",
    )
    rows: list[ModerationDatasetCandidate] = []
    for index in range(count):
        text = _choice(frames, index, 1).format(
            subject=_choice(subjects, index, len(frames)),
            judgment=_choice(judgments, index, len(frames) * len(subjects)),
        ) + _choice(suffixes, index, len(frames) * len(subjects) * len(judgments))
        text = f"{_choice(contexts, index, 1_600)}: {text}; {_choice(audiences, index, 25_600)}."
        rows.append(_candidate("russian_robustness", 100_000 + index, ModerationLabel.POLITICS_IRL, text, [ModerationLabel.POLITICS_IRL]))
    return rows


def _family_and_identity_cases(count: int) -> list[ModerationDatasetCandidate]:
    targets = ("твою семью", "твою маму", "твоего брата", "твою сестру", "твоих родителей")
    insults = ("не трогай", "оскорблять нельзя", "я знаю, где живёт", "не смей впутывать", "оставь в покое")
    identity = ("гомик", "гей", "гетеросексуал", "лесбиянка", "бисексуал")
    hostile = ("ты {identity}, и поэтому тебе здесь не место", "фу, ты {identity}", "из-за того что ты {identity}, уходи")
    neutral = ("он {identity}, это не повод для оскорблений", "сексуальная ориентация — личное дело: {identity}")
    rows: list[ModerationDatasetCandidate] = []
    for index in range(count):
        if index % 3 == 0:
            text = f"{_select(insults, index)} {_select(targets, index // 3)}"
            label = ModerationLabel.THREAT if "знаю" in text else ModerationLabel.TOXIC
            labels = [label]
        elif index % 3 == 1:
            text = _select(hostile, index).format(identity=_select(identity, index // 3))
            label = ModerationLabel.HATE
            labels = [ModerationLabel.HATE, ModerationLabel.TOXIC]
        else:
            text = _select(neutral, index).format(identity=_select(identity, index // 3))
            label = ModerationLabel.SAFE
            labels = [ModerationLabel.SAFE]
        rows.append(_candidate("russian_robustness", 200_000 + index, label, text, labels))
    return rows


def _scam_context_cases(count: int) -> list[ModerationDatasetCandidate]:
    domains = ("точно-не-скам.рф", "steamcomrnunity-login.example", "discord-nitro-free.example", "sber-bonus-pay.example")
    lures = ("куча бесплатного контента", "бесплатные скины", "выплата за регистрацию", "nitro без оплаты")
    asks = ("зайди и авторизуйся", "введи код из смс", "подтверди карту", "введи пароль от аккаунта")
    rows: list[ModerationDatasetCandidate] = []
    for index in range(count):
        text = f"https://{_select(domains, index)} хей, {_select(lures, index // 4)} — {_select(asks, index // 16)}"
        rows.append(_candidate("russian_robustness", 300_000 + index, ModerationLabel.SCAM, text, [ModerationLabel.SCAM, ModerationLabel.URL]))
    return rows


def _select(values: tuple[str, ...], index: int) -> str:
    return values[index % len(values)]


def _choice(values: tuple[str, ...], index: int, divisor: int) -> str:
    return values[(index // divisor) % len(values)]


def _candidate(
    source_bucket: str,
    index: int,
    primary_label: ModerationLabel,
    text: str,
    labels: list[ModerationLabel],
) -> ModerationDatasetCandidate:
    severity = {
        ModerationLabel.SAFE: 0,
        ModerationLabel.PROFANITY: 1,
        ModerationLabel.POLITICS_IRL: 2,
        ModerationLabel.TOXIC: 3,
        ModerationLabel.SCAM: 4,
        ModerationLabel.HATE: 5,
        ModerationLabel.THREAT: 5,
    }.get(primary_label, 2)
    return ModerationDatasetCandidate(
        text=text,
        labels=labels,
        primary_label=primary_label,
        source_bucket=source_bucket,
        source_id=f"{source_bucket}_{index}",
        severity=severity,
        metadata={"generator": "russian_robustness_templates_v1"},
    )
