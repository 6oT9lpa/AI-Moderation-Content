# Dataset schema

Dataset-слой нужен отдельно от обычной истории сообщений. Нельзя превращать `messages` в одну большую ML-таблицу.

## Основные таблицы

### ai_message_events

Стабильное событие анализа сообщения.

Поля: `id`, `platform`, `space_id`, `channel_id`, `message_id`, `user_id`, `event_type`, `source`, `raw_text`, `normalized_text`, `text_hash`, `language`, `has_attachments`, `attachment_count`, `created_at`, `processed_at`, `retention_until`.

### ai_message_features

Признаки текста, поведения и контекста.

Поля: `event_id`, `char_count`, `word_count`, `url_count`, `invite_count`, `mention_count`, `caps_ratio`, `has_url`, `has_invite`, `has_shortener`, `has_mixed_scripts`, `account_age_days`, `member_age_days`, `recent_user_messages_60s`, `user_warnings_count`, `features_json`, `created_at`.

### ai_media_attachments

Дешёвый анализ вложений.

Поля: `id`, `event_id`, `attachment_id`, `file_type`, `content_type`, `file_size`, `width`, `height`, `sha256`, `phash`, `dhash`, `ahash`, `ocr_text`, `ocr_confidence`, `ocr_text_hash`, `known_scam_hash_match`, `storage_uri`, `created_at`.

### ai_analysis_results

Результаты каждого этапа pipeline.

Поля: `id`, `event_id`, `stage`, `model_name`, `model_version`, `output_json`, `labels_json`, `confidence`, `risk_score`, `risk_breakdown_json`, `latency_ms`, `error`, `created_at`.

### ai_moderation_decisions

Финальное решение Decision Engine.

Поля: `id`, `event_id`, `policy_version`, `decision_action`, `severity`, `reason_code`, `reason_text`, `action_taken`, `action_success`, `platform_error`, `review_status`, `created_at`.

### ai_feedback_labels

Ручная разметка и исправления.

Поля: `id`, `event_id`, `labels_json`, `primary_label`, `severity`, `recommended_action`, `moderator_id`, `feedback_type`, `is_false_positive`, `is_false_negative`, `needs_context`, `annotator_confidence`, `annotation_source`, `notes`, `created_at`.

## Export для обучения

Training export должен собираться отдельным query/view. Он не должен брать все записи подряд. Нужны фильтры по `source`, `language`, `quality`, `feedback_type`, `retention` и балансу классов.

## Privacy

Для ML-export использовать hash для user, server и channel id. Токены, email, телефоны, invite-коды и приватные ссылки должны маскироваться.
