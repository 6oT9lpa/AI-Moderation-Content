from __future__ import annotations

import hashlib
from typing import Any

from psycopg.types.json import Jsonb

from src.domain.action.action_execution_status import ActionExecutionStatus
from src.domain.dataset.dataset_collector_repository import DatasetCollectorRepository
from src.domain.dto.dataset.dataset_collection_record import DatasetCollectionRecord
from src.domain.dto.dataset.dataset_collection_result import DatasetCollectionResult
from src.infrastructure.database.connection import DatabaseConnection
from src.infrastructure.logging.logger import get_logger
from src.modules.dataset.media_analysis_sanitizer import MediaAnalysisSanitizer

logger = get_logger(__name__)


class PostgresqlDatasetCollectorRepository(DatasetCollectorRepository):
    def __init__(
        self,
        database: DatabaseConnection,
        *,
        media_analysis_sanitizer: MediaAnalysisSanitizer | None = None,
    ) -> None:
        self._database = database
        self._media_analysis_sanitizer = media_analysis_sanitizer or MediaAnalysisSanitizer()

    async def save_collection(
        self,
        record: DatasetCollectionRecord,
    ) -> DatasetCollectionResult:
        event_id = await self._upsert_event(record)
        media_audit = self._media_analysis_sanitizer.sanitize(record.media_analysis) if record.media_analysis else None
        await self._upsert_features(event_id, record, media_audit)
        if record.media_analysis is not None:
            await self._upsert_media_attachments(event_id, record, media_audit)
            await self._insert_media_analysis(event_id, record, media_audit)
        await self._insert_rule_analysis(event_id, record)
        decision_id = await self._insert_decision(event_id, record)

        if record.feedback is not None:
            await self._insert_feedback(event_id, decision_id, record)

        training_example = record.training_example.model_copy(update={"event_id": event_id})
        logger.info(
            "Dataset collection persisted event_id=%s decision_id=%s message_id=%s",
            event_id,
            decision_id,
            record.message_id,
        )
        return DatasetCollectionResult(
            event_id=event_id,
            decision_id=decision_id,
            training_example=training_example,
        )

    async def _upsert_event(self, record: DatasetCollectionRecord) -> int:
        result = await self._database.execute(
            """
            INSERT INTO ai_message_events (
                platform,
                message_id,
                guild_id,
                channel_id,
                user_id,
                event_type,
                source,
                raw_text,
                normalized_text,
                text_hash,
                language,
                reply_to_message_id,
                has_attachments,
                attachment_count,
                created_at,
                processed_at,
                retention_until
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (guild_id, message_id) DO UPDATE SET
                platform = EXCLUDED.platform,
                channel_id = EXCLUDED.channel_id,
                user_id = EXCLUDED.user_id,
                event_type = EXCLUDED.event_type,
                source = EXCLUDED.source,
                raw_text = EXCLUDED.raw_text,
                normalized_text = EXCLUDED.normalized_text,
                text_hash = EXCLUDED.text_hash,
                language = EXCLUDED.language,
                reply_to_message_id = EXCLUDED.reply_to_message_id,
                has_attachments = EXCLUDED.has_attachments,
                attachment_count = EXCLUDED.attachment_count,
                processed_at = EXCLUDED.processed_at,
                retention_until = EXCLUDED.retention_until
            RETURNING id
            """,
            [
                record.platform,
                record.message_id,
                record.guild_id,
                record.channel_id,
                record.user_id,
                record.event_type,
                record.source.value,
                record.text.raw_text,
                record.text.normalized_text,
                record.text.text_hash,
                record.language,
                record.reply_to_message_id,
                record.has_attachments,
                record.attachment_count,
                record.created_at,
                record.processed_at,
                record.retention_until,
            ],
        )
        if result.lastrowid is None:
            raise RuntimeError(f"Dataset event was not returned message_id={record.message_id}")

        return result.lastrowid

    async def _upsert_features(
        self,
        event_id: int,
        record: DatasetCollectionRecord,
        media_audit: dict[str, Any] | None,
    ) -> None:
        features = record.features
        metadata = {
            **record.metadata,
            "media_analysis": media_audit,
        }
        await self._database.execute(
            """
            INSERT INTO ai_message_features (
                event_id,
                char_count,
                token_count,
                word_count,
                line_count,
                url_count,
                invite_count,
                mention_count,
                role_mention_count,
                channel_mention_count,
                emoji_count,
                emoji_ratio,
                caps_ratio,
                repeated_char_score,
                duplicate_text_score,
                has_url,
                has_invite,
                has_shortener,
                has_mixed_scripts,
                has_zero_width,
                has_suspicious_unicode,
                is_reply,
                account_age_days,
                member_age_days,
                recent_user_messages_10s,
                recent_user_messages_60s,
                recent_user_messages_10m,
                repeated_messages_10m,
                features_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO UPDATE SET
                char_count = EXCLUDED.char_count,
                token_count = EXCLUDED.token_count,
                word_count = EXCLUDED.word_count,
                line_count = EXCLUDED.line_count,
                url_count = EXCLUDED.url_count,
                invite_count = EXCLUDED.invite_count,
                mention_count = EXCLUDED.mention_count,
                role_mention_count = EXCLUDED.role_mention_count,
                channel_mention_count = EXCLUDED.channel_mention_count,
                emoji_count = EXCLUDED.emoji_count,
                emoji_ratio = EXCLUDED.emoji_ratio,
                caps_ratio = EXCLUDED.caps_ratio,
                repeated_char_score = EXCLUDED.repeated_char_score,
                duplicate_text_score = EXCLUDED.duplicate_text_score,
                has_url = EXCLUDED.has_url,
                has_invite = EXCLUDED.has_invite,
                has_shortener = EXCLUDED.has_shortener,
                has_mixed_scripts = EXCLUDED.has_mixed_scripts,
                has_zero_width = EXCLUDED.has_zero_width,
                has_suspicious_unicode = EXCLUDED.has_suspicious_unicode,
                is_reply = EXCLUDED.is_reply,
                account_age_days = EXCLUDED.account_age_days,
                member_age_days = EXCLUDED.member_age_days,
                recent_user_messages_10s = EXCLUDED.recent_user_messages_10s,
                recent_user_messages_60s = EXCLUDED.recent_user_messages_60s,
                recent_user_messages_10m = EXCLUDED.recent_user_messages_10m,
                repeated_messages_10m = EXCLUDED.repeated_messages_10m,
                features_json = EXCLUDED.features_json
            """,
            [
                event_id,
                features.get("text_length", 0),
                features.get("token_count", 0),
                features.get("word_count", 0),
                features.get("line_count", 0),
                features.get("url_count", 0),
                features.get("invite_count", 0),
                features.get("mention_count", 0),
                features.get("role_mention_count", 0),
                features.get("channel_mention_count", 0),
                features.get("emoji_count", 0),
                features.get("emoji_ratio", 0),
                features.get("uppercase_ratio", 0),
                features.get("repeated_char_score", 0),
                features.get("duplicate_text_score", 0),
                features.get("has_url", False),
                features.get("has_invite", False),
                features.get("has_shortener", False),
                features.get("has_mixed_scripts", False),
                features.get("has_zero_width", False),
                features.get("has_suspicious_unicode", False),
                record.reply_to_message_id is not None,
                features.get("account_age_days"),
                features.get("member_age_days"),
                features.get("recent_user_messages_10s", 0),
                features.get("recent_user_messages_60s", 0),
                features.get("recent_user_messages_10m", 0),
                features.get("repeated_messages_10m", 0),
                Jsonb(
                    {
                        **features,
                        **metadata,
                        "training_example": record.training_example.model_dump(mode="json"),
                    }
                ),
            ],
        )

    async def _insert_rule_analysis(self, event_id: int, record: DatasetCollectionRecord) -> None:
        rule_result = record.rule_evaluation
        await self._database.execute(
            """
            INSERT INTO ai_analysis_results (
                event_id,
                stage,
                model_name,
                model_version,
                input_version,
                output_json,
                label,
                labels_json,
                confidence,
                probabilities_json,
                rule_matches_json,
                risk_score,
                risk_breakdown_json,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                event_id,
                "rule_engine",
                "rule_engine",
                rule_result.policy_version,
                rule_result.policy_id,
                Jsonb(rule_result.model_dump(mode="json")),
                rule_result.primary_label.value,
                Jsonb([label.value for label in rule_result.labels]),
                rule_result.confidence,
                Jsonb({}),
                Jsonb(rule_result.matched_rules),
                round(rule_result.risk_score),
                Jsonb([item.model_dump(mode="json") for item in rule_result.risk_breakdown]),
                rule_result.created_at,
            ],
        )

    async def _upsert_media_attachments(
        self,
        event_id: int,
        record: DatasetCollectionRecord,
        media_audit: dict[str, Any] | None,
    ) -> None:
        media_analysis = record.media_analysis
        if media_analysis is None or media_audit is None:
            return

        audit_by_attachment_id = {
            str(attachment_audit.get("attachment_id")): attachment_audit
            for attachment_audit in media_audit.get("attachments", [])
            if isinstance(attachment_audit, dict)
        }

        for attachment in media_analysis.attachments:
            attachment_audit = audit_by_attachment_id.get(attachment.attachment_id, {})
            ocr_text = str(attachment_audit.get("ocr_text") or "")
            ocr_error = attachment_audit.get("ocr_error")
            ocr_features = attachment.ocr_features
            ocr_text_hash = (
                hashlib.sha256(ocr_text.encode("utf-8")).hexdigest()
                if ocr_text
                else None
            )
            await self._database.execute(
                """
                INSERT INTO ai_media_attachments (
                    event_id, attachment_id, file_name, file_type, content_type, file_size,
                    width, height, aspect_ratio, sha256, phash, dhash, ahash,
                    is_screenshot_like, ocr_text, ocr_language, ocr_confidence, ocr_status, ocr_error,
                    ocr_text_hash,
                    ocr_has_money, ocr_has_casino, ocr_has_crypto, ocr_has_bonus,
                    ocr_has_payment_words, ocr_has_fake_news, ocr_text_density,
                    ocr_money_amounts_json, ocr_domains_json, ocr_keywords_json,
                    known_scam_hash_match, scam_subtype, storage_uri
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT (event_id, attachment_id) DO UPDATE SET
                    file_name = EXCLUDED.file_name,
                    file_type = EXCLUDED.file_type,
                    content_type = EXCLUDED.content_type,
                    file_size = EXCLUDED.file_size,
                    width = EXCLUDED.width,
                    height = EXCLUDED.height,
                    aspect_ratio = EXCLUDED.aspect_ratio,
                    sha256 = EXCLUDED.sha256,
                    phash = EXCLUDED.phash,
                    dhash = EXCLUDED.dhash,
                    ahash = EXCLUDED.ahash,
                    is_screenshot_like = EXCLUDED.is_screenshot_like,
                    ocr_text = EXCLUDED.ocr_text,
                    ocr_language = EXCLUDED.ocr_language,
                    ocr_confidence = EXCLUDED.ocr_confidence,
                    ocr_status = EXCLUDED.ocr_status,
                    ocr_error = EXCLUDED.ocr_error,
                    ocr_text_hash = EXCLUDED.ocr_text_hash,
                    ocr_has_money = EXCLUDED.ocr_has_money,
                    ocr_has_casino = EXCLUDED.ocr_has_casino,
                    ocr_has_crypto = EXCLUDED.ocr_has_crypto,
                    ocr_has_bonus = EXCLUDED.ocr_has_bonus,
                    ocr_has_payment_words = EXCLUDED.ocr_has_payment_words,
                    ocr_has_fake_news = EXCLUDED.ocr_has_fake_news,
                    ocr_text_density = EXCLUDED.ocr_text_density,
                    ocr_money_amounts_json = EXCLUDED.ocr_money_amounts_json,
                    ocr_domains_json = EXCLUDED.ocr_domains_json,
                    ocr_keywords_json = EXCLUDED.ocr_keywords_json,
                    known_scam_hash_match = EXCLUDED.known_scam_hash_match,
                    scam_subtype = EXCLUDED.scam_subtype,
                    storage_uri = EXCLUDED.storage_uri
                """,
                [
                    event_id,
                    attachment.attachment_id,
                    attachment.metadata.file_name,
                    attachment.metadata.content_type.removeprefix("image/"),
                    attachment.metadata.content_type,
                    attachment.metadata.file_size,
                    attachment.metadata.width,
                    attachment.metadata.height,
                    attachment.metadata.aspect_ratio,
                    attachment.hashes.sha256,
                    attachment.hashes.phash,
                    attachment.hashes.dhash,
                    attachment.hashes.ahash,
                    attachment.metadata.is_screenshot_like,
                    ocr_text or None,
                    attachment.ocr_result.language,
                    attachment.ocr_result.confidence,
                    attachment.ocr_result.status.value,
                    str(ocr_error) if ocr_error else None,
                    ocr_text_hash,
                    ocr_features.has_money_amount,
                    ocr_features.has_casino,
                    ocr_features.has_crypto,
                    ocr_features.has_bonus_or_promo,
                    ocr_features.has_payment_words,
                    ocr_features.has_fake_news,
                    ocr_features.text_density,
                    Jsonb(list(ocr_features.money_amounts)),
                    Jsonb(list(ocr_features.domains)),
                    Jsonb(ocr_features.to_dict()),
                    attachment.known_scam_hash_match,
                    media_analysis.scam_subtype.value if media_analysis.scam_subtype else None,
                    None,
                ],
            )

    async def _insert_media_analysis(
        self,
        event_id: int,
        record: DatasetCollectionRecord,
        media_audit: dict[str, Any] | None,
    ) -> None:
        media_analysis = record.media_analysis
        if media_analysis is None or media_audit is None:
            return
        confidence = max((match.confidence for match in media_analysis.rule_matches), default=None)
        primary_label = next(
            (label for label in media_analysis.labels if label.value == "SCAM"),
            media_analysis.labels[0] if media_analysis.labels else None,
        )
        await self._database.execute(
            """
            INSERT INTO ai_analysis_results (
                event_id, stage, model_name, input_version, output_json, label, labels_json,
                confidence, probabilities_json, rule_matches_json, risk_score, risk_breakdown_json, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """,
            [
                event_id,
                "ocr_rule_engine",
                "cpu_media_analyzer",
                "media_analyzer_v1",
                Jsonb(media_audit),
                primary_label.value if primary_label else None,
                Jsonb([label.value for label in media_analysis.labels]),
                confidence,
                Jsonb({}),
                Jsonb([match.to_dict() for match in media_analysis.rule_matches]),
                media_analysis.risk.score,
                Jsonb(media_analysis.risk.to_dict()["breakdown"]),
            ],
        )

    async def _insert_decision(self, event_id: int, record: DatasetCollectionRecord) -> int | None:
        action_status = record.action_result.status if record.action_result else None
        action_success = self._is_action_success(action_status)
        result = await self._database.execute(
            """
            INSERT INTO ai_moderation_decisions (
                event_id,
                policy_version,
                decision_action,
                severity,
                reason_code,
                reason_text,
                action_taken,
                action_success,
                platform_error,
                review_status,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            [
                event_id,
                record.decision.policy_version,
                record.decision.decision_action.value,
                record.decision.severity,
                record.decision.reason,
                record.decision.reason,
                record.action_result is not None,
                action_success,
                self._extract_platform_error(record),
                self._review_status(record),
                record.decision.created_at,
            ],
        )
        return result.lastrowid

    async def _insert_feedback(
        self,
        event_id: int,
        decision_id: int | None,
        record: DatasetCollectionRecord,
    ) -> None:
        feedback = record.feedback
        if feedback is None:
            return

        await self._database.execute(
            """
            INSERT INTO ai_feedback_labels (
                event_id,
                decision_id,
                labels_json,
                primary_label,
                scam_subtype,
                severity,
                recommended_action,
                moderator_id,
                feedback_type,
                is_false_positive,
                is_false_negative,
                needs_context,
                annotator_confidence,
                annotation_source,
                notes,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """,
            [
                event_id,
                decision_id,
                Jsonb([label.value for label in feedback.labels]),
                feedback.primary_label.value if feedback.primary_label else None,
                feedback.scam_subtype,
                feedback.severity,
                feedback.recommended_action.value if feedback.recommended_action else None,
                feedback.moderator_id,
                feedback.feedback_type.value,
                feedback.is_false_positive,
                feedback.is_false_negative,
                feedback.needs_context,
                feedback.annotator_confidence,
                feedback.annotation_source,
                feedback.notes,
            ],
        )

    def _is_action_success(self, status: ActionExecutionStatus | None) -> bool | None:
        if status is None:
            return None

        return status in {
            ActionExecutionStatus.SUCCESS,
            ActionExecutionStatus.DRY_RUN,
            ActionExecutionStatus.PARTIAL_SUCCESS,
            ActionExecutionStatus.SKIPPED,
        }

    def _extract_platform_error(self, record: DatasetCollectionRecord) -> str | None:
        if record.action_result is None:
            return None

        errors = [step.error for step in record.action_result.steps if step.error]
        return "; ".join(errors) if errors else None

    def _review_status(self, record: DatasetCollectionRecord) -> str:
        if record.feedback is not None:
            return record.feedback.feedback_type.value

        if record.decision.decision_action.value == "REVIEW":
            return "pending"

        return "not_required"
