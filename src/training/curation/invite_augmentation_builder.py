from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.curation.dataset_split_assigner import DatasetSplitAssigner
from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema


class InviteAugmentationBuilder:
    _RU_INTROS = (
        "Заходи к нам",
        "Присоединяйся к сообществу",
        "Вот приглашение",
        "Открыли новый сервер",
        "Ждём новых участников",
        "Подключайся к нашему серверу",
        "Ссылка для входа",
        "Приглашение для друзей",
        "Добро пожаловать к нам",
        "Вступай в наше сообщество",
        "Переходим на новый сервер",
        "Наш Discord открыт",
    )
    _RU_COMMUNITIES = (
        "игровой сервер",
        "сервер по Minecraft",
        "сервер по Counter-Strike",
        "сервер по Dota",
        "сервер по Roblox",
        "чат по Python",
        "чат разработчиков",
        "учебная группа",
        "клуб настольных игр",
        "аниме-сообщество",
        "музыкальный клуб",
        "сервер художников",
        "книжный клуб",
        "киберспортивная команда",
        "группа поиска тиммейтов",
        "чат для общения",
        "сервер нашего клана",
        "сообщество стримеров",
        "сервер турнира",
        "клуб любителей кино",
        "сервер взаимопомощи",
        "чат игрового проекта",
        "сообщество моддеров",
        "сервер фанатов",
        "группа совместных игр",
        "сервер для новичков",
        "сервер команды",
        "чат участников курса",
        "сервер локального сообщества",
        "клуб по интересам",
    )
    _RU_TAILS = (
        "Ссылка: <INVITE>",
        "Приглашение: <INVITE>",
        "Вход здесь — <INVITE>",
        "<INVITE> <DISCORD_ROLE_MENTION>",
        "Переходи по приглашению <INVITE>",
    )
    _EN_INTROS = (
        "Join us",
        "Welcome to our community",
        "Here is the invitation",
        "We opened a new server",
        "New members are welcome",
        "Connect to our Discord",
        "Server invitation",
        "Invite for the community",
        "Move to our new server",
        "Our Discord is open",
    )
    _EN_COMMUNITIES = (
        "gaming server",
        "Minecraft community",
        "developer chat",
        "study group",
        "book club",
        "music community",
        "art server",
        "tournament server",
        "team server",
        "movie club",
        "streamer community",
        "modding community",
        "server for beginners",
        "course chat",
        "local community",
        "tabletop club",
        "clan server",
        "scrim group",
        "project server",
        "general chat",
    )
    _EN_TAILS = (
        "Link: <INVITE>",
        "Invite: <INVITE>",
        "Join here — <INVITE>",
        "<INVITE> <DISCORD_ROLE_MENTION>",
    )

    def __init__(
        self,
        *,
        schema: ModerationDatasetSchema,
        split_assigner: DatasetSplitAssigner,
        target_rows: int = 2_200,
    ) -> None:
        if target_rows <= 0:
            raise ValueError("target_rows must be positive")
        self._schema = schema
        self._split_assigner = split_assigner
        self._target_rows = target_rows

    def build(self, *, output_dir: Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        counts: Counter[str] = Counter()
        handles = {
            split: (output_dir / f"{split}.jsonl").open(
                "w",
                encoding="utf-8",
                newline="\n",
            )
            for split in ("train", "validation")
        }

        seen: set[str] = set()
        try:
            for text in self._candidate_texts():
                normalized = " ".join(text.casefold().split())
                if normalized in seen:
                    continue
                seen.add(normalized)

                split = self._split_assigner.assign(text)
                record = self._schema.build_row(
                    text=text,
                    labels=(ModerationLabel.INVITE, ModerationLabel.URL),
                    severity=1,
                    record_id=f"invite_aug_{len(seen) - 1}",
                )
                handles[split].write(
                    json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
                counts[f"written_{split}"] += 1
                if len(seen) >= self._target_rows:
                    break
        finally:
            for handle in handles.values():
                handle.close()

        if len(seen) != self._target_rows:
            raise RuntimeError(
                f"Invite augmentation produced {len(seen)} rows, "
                f"expected {self._target_rows}"
            )

        return {
            "source": "controlled_bilingual_invite_templates",
            "license": "project-generated",
            "target_rows": self._target_rows,
            "counts": dict(counts),
        }

    def _candidate_texts(self) -> Iterator[str]:
        for intro in self._RU_INTROS:
            for community in self._RU_COMMUNITIES:
                for tail in self._RU_TAILS:
                    yield f"{intro}: {community}. {tail}"

        for intro in self._EN_INTROS:
            for community in self._EN_COMMUNITIES:
                for tail in self._EN_TAILS:
                    yield f"{intro}: {community}. {tail}"
