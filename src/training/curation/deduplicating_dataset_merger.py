from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from src.training.curation.moderation_dataset_schema import ModerationDatasetSchema
from src.training.curation.sensitive_topic_matcher import SensitiveTopicMatcher


class DeduplicatingDatasetMerger:
    _TRAIN_MASK = 1
    _VALIDATION_MASK = 2
    _BATCH_SIZE = 10_000

    def __init__(self, *, schema: ModerationDatasetSchema) -> None:
        self._schema = schema

    def merge_into(
        self,
        *,
        sources: Iterable[tuple[str, Path, Path]],
        target_dir: Path,
    ) -> dict[str, Any]:
        source_list = list(sources)
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        database_path = target_dir / f".sensitive-topic-merge-{stamp}.sqlite3"
        train_temp = target_dir / f".train-{stamp}.tmp"
        validation_temp = target_dir / f".validation-{stamp}.tmp"

        input_counts: dict[str, dict[str, int]] = {}
        connection = sqlite3.connect(database_path)
        try:
            self._initialize_database(connection)
            for source_rank, (source_name, train_path, validation_path) in enumerate(source_list):
                input_counts[source_name] = {
                    "train": self._load_file(
                        connection,
                        path=train_path,
                        split_mask=self._TRAIN_MASK,
                        source_rank=source_rank,
                    ),
                    "validation": self._load_file(
                        connection,
                        path=validation_path,
                        split_mask=self._VALIDATION_MASK,
                        source_rank=source_rank,
                    ),
                }

            database_stats = self._database_stats(connection)
            train_rows = self._write_split(
                connection,
                split="train",
                output_path=train_temp,
            )
            validation_rows = self._write_split(
                connection,
                split="validation",
                output_path=validation_temp,
            )
            self._validate_output(train_temp, expected_rows=train_rows)
            self._validate_output(validation_temp, expected_rows=validation_rows)

            backup_dir = target_dir / f"backup_before_sensitive_curation_{stamp}"
            backup_dir.mkdir(parents=False, exist_ok=False)
            original_hashes = self._backup_targets(target_dir=target_dir, backup_dir=backup_dir)
            output_hashes = {
                "train.jsonl": self._sha256(train_temp),
                "validation.jsonl": self._sha256(validation_temp),
            }

            os.replace(train_temp, target_dir / "train.jsonl")
            os.replace(validation_temp, target_dir / "validation.jsonl")

            return {
                "sources": [name for name, _, _ in source_list],
                "input_counts": input_counts,
                "database": database_stats,
                "result": {
                    "train_rows": train_rows,
                    "validation_rows": validation_rows,
                    "normalized_duplicates": 0,
                    "cross_split_overlap": 0,
                },
                "backup_dir": str(backup_dir),
                "original_sha256": original_hashes,
                "output_sha256": output_hashes,
            }
        finally:
            connection.close()
            for temporary_path in (database_path, train_temp, validation_temp):
                if temporary_path.exists():
                    temporary_path.unlink()

    @staticmethod
    def _initialize_database(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA temp_store=MEMORY")
        connection.execute(
            """
            CREATE TABLE records (
                normalized_text TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                label_mask INTEGER NOT NULL,
                severity INTEGER NOT NULL,
                split_mask INTEGER NOT NULL,
                source_rank INTEGER NOT NULL
            ) WITHOUT ROWID
            """
        )

    def _load_file(
        self,
        connection: sqlite3.Connection,
        *,
        path: Path,
        split_mask: int,
        source_rank: int,
    ) -> int:
        statement = """
            INSERT INTO records (
                normalized_text,
                text,
                label_mask,
                severity,
                split_mask,
                source_rank
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(normalized_text) DO UPDATE SET
                label_mask = records.label_mask | excluded.label_mask,
                severity = MAX(records.severity, excluded.severity),
                split_mask = records.split_mask | excluded.split_mask,
                text = CASE
                    WHEN excluded.source_rank < records.source_rank THEN excluded.text
                    ELSE records.text
                END,
                source_rank = MIN(records.source_rank, excluded.source_rank)
        """
        batch: list[tuple[str, str, int, int, int, int]] = []
        rows = 0

        with path.open("r", encoding="utf-8-sig") as source:
            for line_number, raw in enumerate(source, 1):
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc

                normalized = self._schema.normalize_row(row)
                batch.append(
                    (
                        SensitiveTopicMatcher.normalize_text(normalized["text"]),
                        normalized["text"],
                        self._schema.row_to_mask(normalized),
                        int(normalized["severity"]),
                        split_mask,
                        source_rank,
                    )
                )
                rows += 1
                if len(batch) >= self._BATCH_SIZE:
                    connection.executemany(statement, batch)
                    connection.commit()
                    batch.clear()

        if batch:
            connection.executemany(statement, batch)
            connection.commit()
        return rows

    @staticmethod
    def _database_stats(connection: sqlite3.Connection) -> dict[str, int]:
        total = int(connection.execute("SELECT COUNT(*) FROM records").fetchone()[0])
        cross_split = int(
            connection.execute(
                "SELECT COUNT(*) FROM records WHERE split_mask = ?",
                (DeduplicatingDatasetMerger._TRAIN_MASK | DeduplicatingDatasetMerger._VALIDATION_MASK,),
            ).fetchone()[0]
        )
        validation = int(
            connection.execute(
                "SELECT COUNT(*) FROM records WHERE (split_mask & ?) != 0",
                (DeduplicatingDatasetMerger._VALIDATION_MASK,),
            ).fetchone()[0]
        )
        return {
            "unique_normalized_texts": total,
            "texts_seen_in_both_splits": cross_split,
            "validation_priority_rows": validation,
        }

    def _write_split(
        self,
        connection: sqlite3.Connection,
        *,
        split: str,
        output_path: Path,
    ) -> int:
        if split == "validation":
            where = "(split_mask & ?) != 0"
            parameter = self._VALIDATION_MASK
        elif split == "train":
            where = "(split_mask & ?) = 0"
            parameter = self._VALIDATION_MASK
        else:
            raise ValueError(f"Unsupported split: {split}")

        rows = 0
        query = (
            "SELECT text, label_mask, severity "
            f"FROM records WHERE {where} ORDER BY normalized_text"
        )
        with output_path.open("w", encoding="utf-8", newline="\n") as output:
            for rows, (text, label_mask, severity) in enumerate(
                connection.execute(query, (parameter,)),
                1,
            ):
                record = self._schema.build_row(
                    text=text,
                    labels=self._schema.mask_to_labels(int(label_mask)),
                    severity=int(severity),
                    record_id=rows,
                )
                output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        return rows

    def _validate_output(self, path: Path, *, expected_rows: int) -> None:
        rows = 0
        with path.open("r", encoding="utf-8") as source:
            for line_number, raw in enumerate(source, 1):
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid output JSON at {path}:{line_number}") from exc
                self._schema.validate_row(row)
                rows += 1
        if rows != expected_rows:
            raise ValueError(f"Expected {expected_rows} rows in {path}, found {rows}")

    def _backup_targets(self, *, target_dir: Path, backup_dir: Path) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for filename in ("train.jsonl", "validation.jsonl"):
            source = target_dir / filename
            target = backup_dir / filename
            hashes[filename] = self._sha256(source)
            shutil.copy2(source, target)
            if self._sha256(target) != hashes[filename]:
                raise ValueError(f"Backup checksum mismatch for {filename}")
        return hashes

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
