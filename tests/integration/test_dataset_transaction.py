import os
from dataclasses import dataclass

import pytest

from src.domain.dataset.dataset_collector_repository import DatasetCollectorRepository
from src.domain.dataset.feedback_type import FeedbackType
from src.domain.dto.dataset.dataset_collection_input import DatasetCollectionInput
from src.domain.dto.dataset.dataset_collection_result import DatasetCollectionResult
from src.domain.dto.dataset.dataset_feedback_label import DatasetFeedbackLabel
from src.domain.moderation.moderation_label import ModerationLabel
from src.infrastructure.database.connection import DatabaseConnection
from src.infrastructure.repository.postgresql_dataset_collector_repository import (
    PostgresqlDatasetCollectorRepository,
)
from src.modules.dataset.dataset_collector import DatasetCollector
from tests.modules.dataset.test_dataset_collector import _run_text_pipeline

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_POSTGRESQL_URL"),
    reason="TEST_POSTGRESQL_URL is required for destructive disposable-database integration tests",
)


@dataclass
class _CaptureRepository(DatasetCollectorRepository):
    record: object | None = None

    async def save_collection(self, record):
        self.record = record
        return DatasetCollectionResult(
            event_id=1,
            decision_id=1,
            training_example=record.training_example.model_copy(update={"event_id": 1}),
        )


async def _collection_record():
    capture = _CaptureRepository()
    context, rules, decision = await _run_text_pipeline(
        "join https://discord.gg/AtomicTest"
    )
    await DatasetCollector(capture).collect(
        DatasetCollectionInput(
            context=context,
            rule_evaluation=rules,
            decision=decision,
            feedback=DatasetFeedbackLabel(
                labels=(ModerationLabel.SCAM,),
                primary_label=ModerationLabel.SCAM,
                severity=4,
                feedback_type=FeedbackType.CONFIRMED,
                annotation_source="integration-test",
            ),
        )
    )
    assert capture.record is not None
    return capture.record


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failing_stage",
    (
        "_upsert_features",
        "_insert_rule_analysis",
        "_insert_decision",
        "_insert_feedback",
    ),
)
async def test_failure_at_each_dataset_stage_rolls_back_every_row(
    monkeypatch, failing_stage
) -> None:
    database = DatabaseConnection(
        os.environ["TEST_POSTGRESQL_URL"], reconnect_attempts=1
    )
    await database.initialize()
    repository = PostgresqlDatasetCollectorRepository(database)
    record = await _collection_record()

    async def fail(*_args, **_kwargs):
        raise RuntimeError(f"fault at {failing_stage}")

    monkeypatch.setattr(repository, failing_stage, fail)
    try:
        with pytest.raises(RuntimeError, match="fault"):
            await repository.save_collection(record)
        row = await database.fetch_one(
            "SELECT id FROM ai_message_events WHERE platform = %s AND message_id = %s",
            [record.platform, record.message_id],
        )
        assert row is None
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_repeated_dataset_delivery_is_bounded_to_one_event() -> None:
    database = DatabaseConnection(
        os.environ["TEST_POSTGRESQL_URL"], reconnect_attempts=1
    )
    await database.initialize()
    repository = PostgresqlDatasetCollectorRepository(database)
    record = await _collection_record()
    try:
        first = await repository.save_collection(record)
        second = await repository.save_collection(record)
        count = await database.fetch_one(
            "SELECT COUNT(*) AS count FROM ai_message_events WHERE platform = %s AND message_id = %s",
            [record.platform, record.message_id],
        )
        decisions = await database.fetch_one(
            "SELECT COUNT(*) AS count FROM ai_moderation_decisions WHERE event_id = %s",
            [first.event_id],
        )
        feedback = await database.fetch_one(
            "SELECT COUNT(*) AS count FROM ai_feedback_labels WHERE event_id = %s",
            [first.event_id],
        )
        assert first.event_id == second.event_id
        assert int(count["count"]) == 1
        assert int(decisions["count"]) == 1
        assert int(feedback["count"]) == 1
    finally:
        await database.execute(
            "DELETE FROM ai_message_events WHERE platform = %s AND message_id = %s",
            [record.platform, record.message_id],
        )
        await database.close()
