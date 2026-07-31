from psycopg.types.json import Jsonb

from src.application.ports.media.media_analysis_result_repository import MediaAnalysisResultRepository
from src.domain.media.media_analysis_record import MediaAnalysisRecord
from src.domain.media.media_analysis_stage import MediaAnalysisStage
from src.infrastructure.database.connection import DatabaseConnection
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


class PostgresqlMediaAnalysisResultRepository(MediaAnalysisResultRepository):
    def __init__(self, database: DatabaseConnection) -> None:
        self._database = database

    async def save(self, record: MediaAnalysisRecord) -> None:
        await self._database.execute(
            """
            INSERT INTO ai_analysis_results (
                event_id, attachment_id, stage, model_name, model_version,
                input_version, policy_version, output_json, label, labels_json,
                confidence, risk_score, latency_ms, error
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (
                event_id, attachment_id, stage, model_name, model_version,
                input_version, policy_version
            ) DO UPDATE SET
                output_json = EXCLUDED.output_json,
                label = EXCLUDED.label,
                labels_json = EXCLUDED.labels_json,
                confidence = EXCLUDED.confidence,
                risk_score = EXCLUDED.risk_score,
                latency_ms = EXCLUDED.latency_ms,
                error = EXCLUDED.error,
                created_at = CURRENT_TIMESTAMP
            """,
            (
                record.event_id,
                record.attachment_id,
                record.stage.value,
                record.model_name or "unknown",
                record.model_version or "unknown",
                record.input_version,
                record.policy_version,
                Jsonb(record.output),
                record.labels[0] if record.labels else None,
                Jsonb(list(record.labels)),
                record.confidence,
                record.risk_score,
                record.latency_ms,
                record.error_summary,
            ),
        )
        logger.info(
            "Media analysis persisted event_id=%s attachment_id=%s stage=%s model_version=%s",
            record.event_id,
            record.attachment_id,
            record.stage.value,
            record.model_version,
        )

    async def find_compatible(
        self,
        event_id: int,
        attachment_id: str,
        stage: MediaAnalysisStage,
        model_name: str,
        model_version: str,
        input_version: str,
        policy_version: str,
    ) -> MediaAnalysisRecord | None:
        row = await self._database.fetch_one(
            """
            SELECT * FROM ai_analysis_results
            WHERE event_id = %s
              AND attachment_id = %s
              AND stage = %s
              AND model_name = %s
              AND model_version = %s
              AND input_version = %s
              AND policy_version = %s
            LIMIT 1
            """,
            (event_id, attachment_id, stage.value, model_name, model_version, input_version, policy_version),
        )
        if row is None:
            return None
        return MediaAnalysisRecord(
            event_id=int(row["event_id"]),
            attachment_id=str(row["attachment_id"]),
            stage=MediaAnalysisStage(row["stage"]),
            model_name=row.get("model_name"),
            model_version=row.get("model_version"),
            input_version=str(row["input_version"]),
            policy_version=str(row["policy_version"]),
            output=dict(row.get("output_json") or {}),
            labels=tuple(row.get("labels_json") or ()),
            confidence=float(row["confidence"]) if row.get("confidence") is not None else None,
            risk_score=row.get("risk_score"),
            latency_ms=row.get("latency_ms"),
            error_summary=row.get("error"),
        )

