from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.domain.moderation.moderation_label import ModerationLabel
from src.training.datasets.moderation_label_priority import resolve_primary_label
from src.training.rubert.rubert_label_schema import RuBertLabelSchema


SEVERITY_MULTIPLIERS: dict[int, float] = {
    0: 0.0,
    1: 0.5,
    2: 0.8,
    3: 1.0,
    4: 1.2,
    5: 1.5,
}

LABEL_SEVERITY: dict[ModerationLabel, int] = {
    ModerationLabel.SAFE: 0,
    ModerationLabel.URL: 1,
    ModerationLabel.EVASION: 2,
    ModerationLabel.SPAM: 2,
    ModerationLabel.ADVERTISEMENT: 2,
    ModerationLabel.FLOOD: 3,
    ModerationLabel.INVITE: 3,
    ModerationLabel.PROFANITY: 1,
    ModerationLabel.POLITICS_IRL: 2,
    ModerationLabel.TOXIC: 3,
    ModerationLabel.SCAM: 4,
    ModerationLabel.NSFW: 4,
    ModerationLabel.HATE: 5,
    ModerationLabel.THREAT: 5,
    ModerationLabel.IMAGE_SCAM: 4,
}

_URL_PATTERN = re.compile(r"(?:https?://|www\.|<URL>|<URL_DOMAIN:[^>]+>)", re.IGNORECASE)
_INVITE_PATTERN = re.compile(r"(?:<DISCORD_INVITE>|discord(?:app)?\.com/invite/|discord\.gg/)", re.IGNORECASE)
_MASS_MENTION_PATTERN = re.compile(r"(?:@everyone|@here|<DISCORD_(?:USER|ROLE)_MENTION>)", re.IGNORECASE)
_REPEATED_CHARS_PATTERN = re.compile(r"([a-zа-яё0-9])\1{5,}", re.IGNORECASE)
_MIXED_SCRIPT_TOKEN_PATTERN = re.compile(r"(?=\w*[a-z])(?=\w*[а-яё])\w{5,}", re.IGNORECASE)
_CORRUPT_TEXT_PATTERN = re.compile(r"(?:�{2,}|\\ufffd{2,})", re.IGNORECASE)

_PATTERNS: dict[ModerationLabel, tuple[re.Pattern[str], ...]] = {
    ModerationLabel.THREAT: (
        re.compile(r"\b(?:убью|зарежу|покалечу|сломаю\s+(?:лицо|ноги|руки)|найду\s+(?:тебя|адрес))\b", re.IGNORECASE),
        re.compile(r"\b(?:докс(?:ну|ить)?|деанон(?:ю|ить)?|солью\s+(?:адрес|данные))\b", re.IGNORECASE),
        re.compile(r"\b(?:твоя|твой|твою|твоего|твоей)\s+(?:мать|мама|сестра|сестренка|брат|отец|батя).{0,80}\b(?:рабств|похищ|изнасил|убь|зареж|найду)\w*", re.IGNORECASE),
    ),
    ModerationLabel.HATE: (
        re.compile(
            r"\b(?:ненавижу|уничтожить|изгнать|убивать)\s+(?:всех\s+)?"
            r"(?:русских|украинцев|евреев|мусульман|мигрантов|женщин|мужчин|геев|гомосексуалов|лгбт|цыган)\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b(?:нацики|хохлы|жиды|чурки|гомик|пидр|пидор|пидорас|педик)\b", re.IGNORECASE),
    ),
    ModerationLabel.SCAM: (
        re.compile(r"\b(?:бесплатн\w+\s+nitro|free\s+nitro|steam\s+gift|airdrop|crypto|wallet)\b", re.IGNORECASE),
        re.compile(r"\b(?:выиграл\w*|забери\s+приз|получи\s+\d+\s*(?:руб|₽)|удво(?:ю|ение)\s+баланс)\b", re.IGNORECASE),
        re.compile(r"\b(?:казино|ставк\w+|быстр(?:ый|ые)\s+деньг\w+|инвестиц\w+)\b", re.IGNORECASE),
        re.compile(r"\b(?:деньг\w+|бабл\w+|выплат\w+|раздач\w+|помощь\s+с\s+деньг\w+|рубл\w+).{0,100}\b(?:регистрац\w+|регу|перейд\w+|заход\w+|ссылк\w+|кажд\w+)\b", re.IGNORECASE),
        re.compile(r"(?:https?://|<URL>|<URL_DOMAIN:[^>]+>).{0,120}\b(?:5000|10000|рубл\w+|деньг\w+|бабл\w+|раздач\w+|выплат\w+|подар(?:ок|к\w*)|бонус\w*)\b", re.IGNORECASE),
        re.compile(r"\b(?:steam|discord|nitro|скин\w+|cs|кс).{0,100}\b(?:free|бесплатн\w+|раздач\w+|gift|drop|логин|парол\w+|код)\b", re.IGNORECASE),
        re.compile(
            r"\b(?:steamcomrnunity|steamcommunity[-_.](?:login|gift|bonus|drop)|"
            r"discord[-_.](?:nitro|gift|login)|sber[-_.](?:bonus|pay|login)|qiwi[-_.](?:prize|pay)|"
            r"vk[-_.](?:support|security|login)|faceit[-_.](?:drop|gift|login))"
            r"[a-z0-9_.-]*\.(?:example|top|click|gift|shop|ru|com)\b",
            re.IGNORECASE,
        ),
    ),
    ModerationLabel.NSFW: (
        re.compile(r"\b(?:18\+|nsfw|порно|эротик\w*|интим|секс(?:\b|уальн\w*))\b", re.IGNORECASE),
        re.compile(r"\b(?:давать|дать|дал|дала|даю|дам|люблю\s+ей\s+давать|я\s+бы\s+ей\s+дал).{0,40}\b(?:в\s+рот|рот)\b", re.IGNORECASE),
        re.compile(r"\b(?:тво(?:я|ей|ю)\s+)?(?:мам\w+|мать|матер\w+).{0,80}\b(?:в\s+рот|интим\w+|секс\w+|шлюх\w+)\b", re.IGNORECASE),
        re.compile(r"\b(?:малолетн\w+|несовершеннолетн\w+|школьниц\w+|12\s*летн\w+|13\s*летн\w+|14\s*летн\w+|15\s*летн\w+|16\s*летн\w+|17\s*летн\w+).{0,80}\b(?:девочк\w+|телочк\w+|суч\w+|шлюх\w+|контент|канал|ссылк\w+)?\b", re.IGNORECASE),
        re.compile(r"\b(?:12|13|14|15|16|17)\s*(?:летн\w+|лет).{0,80}\b(?:секс\w+|интим\w+|рабств\w+|изнасил\w+)\b", re.IGNORECASE),
        re.compile(r"\b(?:сестренк\w+|сестра|девочк\w+|малолетк\w+).{0,80}\b(?:сексуальн\w+|рабств\w+|изнасил\w+)\b", re.IGNORECASE),
    ),
    ModerationLabel.TOXIC: (
        re.compile(
            r"\b(?:идиот|дебил|дурак|лох|мразь|тварь|урод|чмо|ублюдок|сука|блять|нахуй|мусор|шалава|шлюха)\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b(?:туп(?:ой|ая|ые|ого|ым)|бляд\w*|хуй\w*|пизд\w*|еба\w*|говн\w*)\b", re.IGNORECASE),
        re.compile(r"\b(?:фу|слышь|слыш|выйди|уйди|пошел|пошла).{0,60}\b(?:чел|мусор|лох|гомик|пидор|педик|шалава|тварь)\b", re.IGNORECASE),
        re.compile(r"\b(?:mq|мп|мамке\s+привет).{0,80}\b(?:тебе|твоей|лузер|мусор|не\s+умеешь|после\s+такого)\b", re.IGNORECASE),
        re.compile(r"\b(?:мать|мам\w+).{0,40}\b(?:шлюх\w+|шалав\w+)\b", re.IGNORECASE),
    ),
    ModerationLabel.PROFANITY: (
        re.compile(
            r"\b(?:хуй\w*|хуе\w*|пизд\w*|ебан\w*|ебат\w*|бляд\w*|гондон\w*|долбоеб\w*|бездар[ья]\w*|бездард\w*)\b",
            re.IGNORECASE,
        ),
    ),
    ModerationLabel.POLITICS_IRL: (
        re.compile(
            r"\b(?:зеленск\w*|путин\w*|верховн\w*\s+рад\w*|госдум\w*|кремл\w*|белый\s+дом|президент\w*|правительств\w*|росси\w*|украин\w*|беларус\w*|сша|нато)\b",
            re.IGNORECASE,
        ),
    ),
    ModerationLabel.ADVERTISEMENT: (
        re.compile(r"\b(?:купи|купить|продам|скидк\w*|промокод\w*|прайс\w*|магазин\w*)\b", re.IGNORECASE),
        re.compile(r"\b(?:заказ(?:ать)?|доставка|акци[яи]|реклам\w*|подпишись|лайк|like\+?sub)\b", re.IGNORECASE),
    ),
}


@dataclass(slots=True)
class RelabelStats:
    path: str
    rows: int = 0
    changed: int = 0
    before_primary: Counter[str] = field(default_factory=Counter)
    after_primary: Counter[str] = field(default_factory=Counter)
    before_labels: Counter[str] = field(default_factory=Counter)
    after_labels: Counter[str] = field(default_factory=Counter)
    severity: Counter[int] = field(default_factory=Counter)

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "rows": self.rows,
            "changed": self.changed,
            "before_primary": dict(self.before_primary),
            "after_primary": dict(self.after_primary),
            "before_labels": dict(self.before_labels),
            "after_labels": dict(self.after_labels),
            "severity": dict(self.severity),
        }


class ModerationExportRelabeler:
    def __init__(self, label_schema: RuBertLabelSchema | None = None) -> None:
        self._label_schema = label_schema or RuBertLabelSchema()

    def relabel_file(self, path: Path) -> RelabelStats:
        rows = self._load_rows(path)
        stats = RelabelStats(path=str(path))
        relabeled_rows: list[dict[str, Any]] = []

        for row in rows:
            stats.rows += 1
            before_labels = self._extract_label_names(row)
            before_primary = str(row.get("primary_label") or self._select_primary(before_labels).value)
            stats.before_primary[before_primary] += 1
            stats.before_labels.update(label.value for label in before_labels)

            updated = self.relabel_row(row)
            after_labels = self._extract_label_names(updated)
            after_primary = str(updated.get("primary_label") or self._select_primary(after_labels).value)
            stats.after_primary[after_primary] += 1
            stats.after_labels.update(label.value for label in after_labels)
            stats.severity[int(updated.get("severity") or 0)] += 1
            if self._row_signature(row) != self._row_signature(updated):
                stats.changed += 1
            relabeled_rows.append(updated)

        self._write_rows(path, relabeled_rows)
        return stats

    def relabel_row(self, row: dict[str, Any]) -> dict[str, Any]:
        updated = dict(row)
        text = str(updated.get("model_text") or updated.get("text") or "")
        existing_labels = self._extract_label_names(updated)
        labels = self._normalize_labels(existing_labels | self._analyze_text(text))
        primary_label = self._select_primary(labels)
        severity = max((LABEL_SEVERITY.get(label, 1) for label in labels), default=0)

        updated["primary_label"] = primary_label.value
        updated["severity"] = severity
        updated["severity_multiplier"] = SEVERITY_MULTIPLIERS[severity]
        updated["risk_score"] = 0.0 if labels == {ModerationLabel.SAFE} else float(max(10, severity * 20))
        if "source" in updated:
            updated["source"] = self._normalize_source(str(updated["source"]), primary_label)
        if "decision_action" in updated:
            updated["decision_action"] = "IGNORE" if primary_label == ModerationLabel.SAFE else "REVIEW"

        label_values = [label.value for label in self._sort_labels(labels)]
        if "label_names" in updated or self._looks_like_rubert_split_row(updated):
            updated["label_names"] = label_values
            updated["labels"] = self._label_schema.encode_labels(list(labels))
        else:
            updated["labels"] = label_values

        metadata = dict(updated.get("metadata") or {})
        metadata["relabeler"] = "moderation_export_relabeler_v1"
        metadata["severity_multiplier"] = SEVERITY_MULTIPLIERS[severity]
        updated["metadata"] = metadata
        return updated

    def _analyze_text(self, text: str) -> set[ModerationLabel]:
        haystack = text.casefold()
        labels: set[ModerationLabel] = set()

        if _URL_PATTERN.search(haystack):
            labels.add(ModerationLabel.URL)
        if _INVITE_PATTERN.search(haystack):
            labels.update({ModerationLabel.INVITE, ModerationLabel.URL})
        if _MASS_MENTION_PATTERN.search(haystack):
            labels.add(ModerationLabel.SPAM)
        if _REPEATED_CHARS_PATTERN.search(haystack):
            labels.add(ModerationLabel.SPAM)
        if _MIXED_SCRIPT_TOKEN_PATTERN.search(haystack) or _CORRUPT_TEXT_PATTERN.search(haystack):
            labels.add(ModerationLabel.EVASION)

        for label, patterns in _PATTERNS.items():
            if any(pattern.search(haystack) for pattern in patterns):
                labels.add(label)

        return labels

    def _normalize_labels(self, labels: set[ModerationLabel]) -> set[ModerationLabel]:
        non_safe = {label for label in labels if label != ModerationLabel.SAFE}
        if non_safe:
            return non_safe
        return {ModerationLabel.SAFE}

    def _select_primary(self, labels: set[ModerationLabel]) -> ModerationLabel:
        return resolve_primary_label(labels)

    def _sort_labels(self, labels: set[ModerationLabel]) -> list[ModerationLabel]:
        primary = self._select_primary(labels)
        return [primary, *sorted((label for label in labels if label != primary), key=lambda label: label.value)]

    def _extract_label_names(self, row: dict[str, Any]) -> set[ModerationLabel]:
        values = row.get("label_names")
        if values is None:
            values = row.get("labels") or []
        if self._is_multihot(values):
            values = self._decode_multihot(values)

        labels: set[ModerationLabel] = set()
        for value in values if isinstance(values, list) else []:
            try:
                labels.add(ModerationLabel(str(value)))
            except ValueError:
                continue
        return self._normalize_labels(labels)

    def _decode_multihot(self, values: list[Any]) -> list[str]:
        id2label = self._label_schema.id2label
        return [
            id2label[index]
            for index, value in enumerate(values)
            if float(value) >= 0.5 and index in id2label
        ]

    def _is_multihot(self, values: Any) -> bool:
        return isinstance(values, list) and bool(values) and all(isinstance(value, (int, float, bool)) for value in values)

    def _looks_like_rubert_split_row(self, row: dict[str, Any]) -> bool:
        return "text" in row and "model_text" not in row

    def _normalize_source(self, source: str, primary_label: ModerationLabel) -> str:
        if source.startswith("real_"):
            return "real_safe" if primary_label == ModerationLabel.SAFE else "real_moderated"
        return source

    def _row_signature(self, row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            tuple(sorted(label.value for label in self._extract_label_names(row))),
            row.get("primary_label"),
            row.get("severity"),
            row.get("risk_score"),
        )

    def _load_rows(self, path: Path) -> list[dict[str, Any]]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _write_rows(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as file:
            for row in rows:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
