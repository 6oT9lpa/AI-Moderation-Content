# AI Moderation Content

`AI Moderation Content` - это ядро ИИ-модератора, независимое от конкретной платформы. Это не Discord-бот, не Telegram-бот и пока не API. Цель репозитория - сначала построить сам moderation engine, а уже потом подключать его к Discord, Telegram, веб-панели или HTTP API через тонкие адаптеры.

Главная идея: платформа отдаёт нормализованное сообщение, ядро анализирует текст, вложения, историю пользователя, правила, риск, ML-предсказания и политику, а затем возвращает финальное moderation-решение.

## Лицензия

Проект является proprietary / source-available. Код не является open source.

Без отдельного письменного разрешения нельзя использовать, копировать, изменять, распространять, продавать или внедрять этот код. Коммерческое использование и право менять код после покупки регулируются отдельной коммерческой лицензией.

Основные условия: [LICENSE](LICENSE). Базовый шаблон для покупателей: [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md).

```text
Platform event
  -> Platform-normalized request
  -> Moderation pipeline
  -> Moderation decision
  -> Dataset and audit record
```

## Цели Архитектуры

- Отделить ИИ-модератор от Discord, Telegram и любых будущих платформ.
- Сделать каждое решение объяснимым и воспроизводимым.
- Начать с дешёвого анализа: rules, risk scoring, image hashing и OCR до дорогих LLM/VLM.
- Собирать датасет с первого дня, чтобы потом нормально обучать ruBERT.
- Не давать ИИ прямое право наказывать пользователей. ИИ даёт сигналы, Decision Engine выбирает действие.
- Поддерживать real-time модерацию и offline-процессы: dataset export, обучение, evaluation, regression checks.

## Основной Pipeline

```text
ModerationRequest
  -> Text Preprocessor
  -> Attachment / Media Analyzer
  -> Rule Engine
  -> Risk Scorer
  -> AI Classifier, optional
  -> Qwen Fallback, rare
  -> Decision Engine
  -> Dataset Collector
  -> ModerationResult
```

## Граница Между Платформой И Ядром

Discord, Telegram и будущие интеграции не должны вызывать внутренние модули напрямую. Они должны преобразовывать свои события в нейтральный `ModerationRequest`.

Пример нейтрального входа:

```json
{
  "platform": "discord",
  "space_id": "guild_or_chat_id",
  "channel_id": "channel_or_topic_id",
  "message_id": "platform_message_id",
  "user": {
    "id": "platform_user_id",
    "account_age_days": 12,
    "member_age_days": 4,
    "roles": ["member"]
  },
  "text": "bro @bot",
  "attachments": [
    {
      "id": "attachment_id",
      "type": "image",
      "content_type": "image/png",
      "url": "https://..."
    }
  ],
  "context": {
    "reply_to_message_id": null,
    "last_user_messages": [],
    "recent_actions": []
  }
}
```

Пример нейтрального результата:

```json
{
  "action": "REVIEW",
  "labels": ["SCAM", "IMAGE_SCAM"],
  "severity": 4,
  "risk_score": 86,
  "confidence": 0.82,
  "reason_code": "casino_bonus_image_scam",
  "explanation": "OCR detected casino, bonus and money transfer patterns.",
  "audit_id": "..."
}
```

## Основные Модули

### Contracts

Слой контрактов описывает платформенно-независимые входы, выходы, DTO и enum-значения. Эти контракты должны использовать и Discord-адаптер, и Telegram-адаптер, и будущий API.

Ключевые сущности:

- `ModerationRequest`
- `UserContext`
- `MessageContext`
- `AttachmentContext`
- `RuleResult`
- `RiskResult`
- `AIResult`
- `Decision`
- `DatasetRecord`

### Domain

Domain-слой хранит словарь модерации и правила предметной области, которые не должны зависеть от БД, OCR, PyTorch, Discord или Telegram.

Базовые labels:

- `SAFE`
- `SPAM`
- `ADVERTISEMENT`
- `INVITE`
- `SCAM`
- `TOXIC`
- `HATE`
- `THREAT`
- `NSFW`
- `EVASION`
- `FLOOD`
- `URL`
- `IMAGE_SCAM`

Базовые actions:

- `IGNORE`
- `LOG`
- `REVIEW`
- `WARN`
- `DELETE`
- `DELETE_WARN`
- `TIMEOUT`
- `BAN`

Severity: шкала от `0` до `5`.

### Application

Application-слой оркестрирует весь workflow. Он не должен знать, пришёл запрос из Discord или Telegram.

Отвечает за:

- запуск preprocessing
- запуск media analysis
- запуск rules
- расчёт risk score
- выбор, нужен ли ML
- вызов ruBERT и fallback-моделей
- выбор финального решения
- запись audit/dataset событий

### Text Preprocessor

Подготавливает текст к анализу.

Должен делать:

- Unicode normalize
- lowercase там, где это полезно
- удаление zero-width символов
- нормализацию пробелов
- детект URL
- детект invite-like паттернов
- детект shorteners
- детект mentions
- расчёт caps ratio, emoji ratio, repeated chars
- детект mixed Cyrillic/Latin и suspicious Unicode

Preprocessor не принимает решений и не наказывает пользователей.

### Attachment / Media Analyzer

Обрабатывает image-first scam: случаи, когда текст сообщения выглядит безопасным, а весь скам находится в картинке.

Дешёвый MVP-подход:

```text
image metadata
  -> sha256
  -> pHash / dHash / aHash
  -> known scam hash check
  -> OCR
  -> OCR keyword rules
  -> media risk score
```

Полезные OCR-сигналы:

- казино, бонусы, промокоды
- crypto, USDT, USD
- суммы денег
- пополнение, вывод, перевод
- fake news layout
- reward, giveaway, activate code

Vision-модель не нужна для MVP. Её можно добавить позже как редкий fallback или инструмент ручного review.

### Rule Engine

Ловит очевидные нарушения быстро и дёшево.

Правила делятся на:

- hard rules: known scam domain, forbidden invite, known scam image hash
- soft signals: suspicious URL, caps spam, emoji spam, new account with image, possible ad

Каждое срабатывание правила должно возвращать:

- `rule_id`
- `severity`
- `confidence`
- `reason`
- `evidence`

### Risk Scorer

Объединяет text features, media features, rule matches, user history и policy в риск `0-100`.

Пример сигналов:

```text
has_invite: +40
has_url: +20
new_account: +15
mass_mentions: +30
known_scam_image_hash: +70
ocr_has_casino: +35
ocr_has_money_amount: +25
```

Стартовая маршрутизация:

```text
0-19    -> IGNORE или LOG
20-49   -> LOG
50-74   -> AI Classifier
75-100  -> Decision Engine, AI или REVIEW в зависимости от hard/soft риска
```

### AI Classifier

Основной классификатор - ruBERT-based multi-label classifier.

Важно: `ruBERT-tiny2` - это base encoder, а не готовый модерационный классификатор. Его нужно дообучить с classification head на своём датасете.

Рекомендуемый формат результата:

```json
{
  "labels": ["ADVERTISEMENT", "INVITE"],
  "primary_label": "ADVERTISEMENT",
  "confidence": 0.91,
  "probabilities": {
    "spam": 0.22,
    "advertisement": 0.91,
    "invite": 0.84,
    "toxic": 0.03
  }
}
```

Классификация должна быть multi-label, потому что одно сообщение может быть одновременно `SPAM + INVITE + SCAM`.

### Qwen Fallback

Qwen не должен вызываться на каждое сообщение.

Вызывать только когда:

- ruBERT не уверен
- rules конфликтуют
- нужен контекст
- модератор явно запросил AI review

Если Qwen недоступен, перегружен или слишком долго отвечает, система должна возвращать `REVIEW`, а не блокировать модерацию.

### Decision Engine

Единственный модуль, который выбирает финальное действие.

Входы:

- rule results
- risk score
- AI result
- media result
- user history
- platform policy
- channel/chat policy

Выходы:

- action
- reason code
- severity
- explanation
- флаг human review

Модель никогда не удаляет, не предупреждает и не банит напрямую.

### Текущий Rule Engine И Decision Engine Foundation

На текущем этапе реализован воспроизводимый внутренний pipeline:

```text
TextPreprocessor
  -> preprocessing_rule_matches
  -> PreprocessingSignalAdapter
  -> ModerationSignal[]
  -> ModerationRuleEngine
  -> RuleEvaluationResult
  -> DecisionEngine
  -> ModerationDecision
```

`PreprocessingRuleEngine` остаётся локальным правиловым слоем внутри text preprocessing. Он отвечает только за первичные дешёвые сигналы: `URL`, `INVITE`, `FLOOD`, `SPAM`, `EVASION`.

`PreprocessingRuleConfigLoader` загружает `configs/rules/preprocessing_rules.yaml` и адаптирует его под `configs/rules/moderation_rule_policy.yaml` через `PreprocessingModerationPolicyAdapter`:

- активные preprocessing rules проверяются против `confidence_thresholds` для `PREPROCESSING`;
- labels должны существовать в `label_weights` и `primary_label_priority`;
- severity должен быть описан в `severity_multipliers`;
- `risk_weight` не должен выходить за пределы `risk_score.max`;
- выключенные semantic placeholders не валидируются как реальные сигналы.

Если preprocessing rule настроен так, что Rule Engine потом гарантированно отфильтрует его, загрузка политики падает явно. Это защищает от ситуации, когда preprocessing в логах нашёл сигнал, а moderation layer молча превратил результат в `SAFE`.

`ModerationRuleEngine` находится в `src/modules/rules/` и отвечает за агрегацию сигналов:

- принимает единый формат `ModerationSignal`;
- поддерживает источники `PREPROCESSING`, `RUBERT`, `QWEN`, `OCR`, `IMAGE`, `HISTORY`, `MANUAL`;
- фильтрует сигналы по confidence thresholds;
- считает вклад риска по source weight, label weight, severity multiplier, confidence и `risk_weight` сигнала;
- ограничивает итоговый `risk_score` диапазоном policy;
- выбирает `primary_label`;
- разрешает конфликты вроде `SAFE + harmful labels`, `URL + SCAM`;
- считает `model_agreement` и high-confidence disagreement между будущими моделями;
- возвращает `RuleEvaluationResult`.

`DecisionEngine` находится в `src/modules/decision/` и отвечает только за выбор рекомендуемого действия:

- принимает `RuleEvaluationResult`;
- применяет `DecisionPolicy`;
- выбирает главное `ModerationAction`;
- строит `action_plan` для связанных действий, например `DELETE_WARN -> DELETE + WARN`, `TIMEOUT -> DELETE + TIMEOUT`, `BAN -> DELETE + BAN`;
- учитывает mode: `PASSIVE`, `ACTIVE`, `STRICT`;
- учитывает `dry_run`;
- учитывает label overrides, risk thresholds, minimum confidence, model disagreement и action bundles;
- возвращает `ModerationDecision`;
- не выполняет реальное действие на платформе.

`decision_action` остаётся главным решением для совместимости и аудита. Реальный platform executor должен использовать `ModerationDecision.action_plan.actions`, потому что часть действий обязана выполняться вместе. Связки действий настраиваются в `configs/rules/decision_policy.yaml` через `action_bundles`, без хардкода в `DecisionEngine`.

Политики загружаются из YAML:

- `configs/rules/preprocessing_rules.yaml`
- `configs/rules/moderation_rule_policy.yaml`
- `configs/rules/decision_policy.yaml`

Все YAML-boundary policy models построены на Pydantic с `frozen=True` и `extra="forbid"`, чтобы ошибки в настройках падали явно, а не меняли поведение молча.

Что пока не реализовано:

- реальные RuBERT/Qwen/OCR adapters;
- DB policy repository и scope fallback;
- action executor для Discord/Telegram;
- запись `RuleEvaluationResult` и `ModerationDecision` в БД;
- Dataset Collector как отдельный production-модуль.

### Dataset Collector

Сохраняет данные для обучения, evaluation, debug и audit.

Должен сохранять:

- raw text с контролируемым retention
- normalized text
- OCR text
- features
- media hashes
- rule matches
- risk score и risk breakdown
- AI predictions
- decision
- moderator feedback
- model version
- policy version
- false positive / false negative markers

Dataset layer должен быть отдельным от обычных platform message logs.

## Практичная Схема Данных

Не нужно делать одну огромную таблицу `messages`. Нужен отдельный dataset-слой вокруг message events.

Рекомендуемые таблицы:

- `ai_message_events`
- `ai_message_features`
- `ai_media_attachments`
- `ai_analysis_results`
- `ai_moderation_decisions`
- `ai_feedback_labels`

### `ai_message_events`

Хранит нормализованное событие.

```text
id
platform
space_id
channel_id
thread_id
message_id
user_id
event_type
source
raw_text
normalized_text
text_hash
language
reply_to_message_id
has_attachments
attachment_count
created_at
processed_at
retention_until
```

### `ai_message_features`

Хранит признаки текста, поведения и контекста.

```text
event_id
char_count
token_count
word_count
url_count
invite_count
mention_count
role_mention_count
emoji_count
caps_ratio
repeated_char_score
duplicate_text_score
has_url
has_invite
has_shortener
has_mixed_scripts
has_zero_width
has_suspicious_unicode
is_reply
account_age_days
member_age_days
recent_user_messages_10s
recent_user_messages_60s
recent_user_messages_10m
repeated_messages_10m
user_warnings_count
user_timeouts_count
channel_is_ai_whitelisted
features_json
created_at
```

### `ai_media_attachments`

Хранит дешёвый анализ изображений и вложений.

```text
id
event_id
attachment_id
file_type
content_type
file_size
width
height
aspect_ratio
sha256
phash
dhash
ahash
is_screenshot_like
ocr_text
ocr_language
ocr_confidence
ocr_text_hash
ocr_has_money
ocr_has_casino
ocr_has_crypto
ocr_has_bonus
ocr_has_payment_words
known_scam_hash_match
storage_uri
created_at
```

### `ai_analysis_results`

Хранит результат каждого аналитического этапа.

```text
id
event_id
stage
model_name
model_version
input_version
output_json
label
labels_json
confidence
probabilities_json
rule_matches_json
risk_score
risk_breakdown_json
latency_ms
error
created_at
```

Примеры `stage`:

- `rule_engine`
- `ocr_rule_engine`
- `risk_scorer`
- `rubert_classifier`
- `qwen_fallback`

### `ai_moderation_decisions`

Хранит финальное решение.

```text
id
event_id
policy_version
decision_action
severity
reason_code
reason_text
action_taken
action_success
platform_error
punishment_id
reviewed_by
review_status
created_at
```

### `ai_feedback_labels`

Хранит ручную разметку и исправления модераторов.

```text
id
event_id
labels_json
primary_label
scam_subtype
severity
recommended_action
moderator_id
feedback_type
is_false_positive
is_false_negative
needs_context
annotator_confidence
annotation_source
notes
created_at
```

## Структура Репозитория

```text
src/ai_moderation/
  contracts/              нейтральные requests, responses и DTO
  domain/                 labels, actions, policies и domain concepts
  application/            orchestration и use cases
  preprocessing/          text normalization и feature extraction
  media/                  image hashing, OCR и media rules
  rules/                  hard rules и soft signals
  risk/                   risk scoring
  classifiers/            ruBERT и интерфейсы классификаторов
  fallback/               Qwen fallback и contested-case reasoning
  decisions/              финальные moderation actions
  dataset/                dataset collection, export и feedback flow
  storage/                repositories и database mappings
  model_registry/         model versions и runtime metadata
  evaluation/             offline metrics и regression checks
  training/               training pipelines и dataset preparation
  workers/                background jobs для OCR, ML и exports
  observability/          metrics, tracing и audit logs
  shared/                 shared utilities

configs/
  rules/                  rule definitions
  policies/               default moderation policies
  thresholds/             risk thresholds
  models/                 model runtime configs
  privacy/                retention и anonymization configs

data/
  seed/                   manual seed examples
  raw/                    локальные raw данные
  processed/              обработанные локальные данные
  exports/                training/evaluation exports
  review/                 moderation review samples

models/
  rubert/                 ruBERT artifacts
  qwen/                   Qwen artifacts или runtime pointers
  ocr/                    OCR resources

docs/
  architecture/           architecture notes
  dataset/                dataset schema и export rules
  annotation/             labeling guide
  operations/             local running и deployment notes
  decisions/              ADR-style architecture decisions

scripts/
  dataset/                dataset import/export scripts
  training/               training commands
  evaluation/             evaluation commands
  maintenance/            cleanup и migration helpers

tests/
  unit/
  integration/
  fixtures/
  golden/
```

## Порядок MVP

1. Contracts и нейтральные request/response schemas.
2. Text Preprocessor.
3. Media Analyzer с hashing и OCR.
4. Rule Engine.
5. Risk Scorer.
6. Dataset Collector.
7. Decision Engine в dry-run режиме.
8. Feedback labels.
9. ruBERT baseline.
10. Qwen fallback.

Не начинать с Qwen и ruBERT. Сначала нужен воспроизводимый pipeline и нормальный dataset/audit trail.

## Первый Milestone

Первый milestone - не “умная модель”, а воспроизводимый moderation pipeline:

```text
input message
  -> normalized context
  -> features
  -> rules
  -> risk
  -> dry-run decision
  -> dataset record
```

Definition of Done:

- Любая платформа может создать нейтральный `ModerationRequest`.
- Pipeline обрабатывает text-only и image messages.
- Каждый этап пишет structured result.
- Каждое финальное решение имеет reason code.
- Dataset export может собрать training rows.
- Система может работать без ruBERT и без Qwen.

## Не Цели Первой Версии

- Нет Discord-бота.
- Нет Telegram-бота.
- Нет публичного HTTP API.
- Нет dashboard.
- Нет автоматических банов.
- Нет vision model в hot path.
- Нет LLM-вызова на каждое сообщение.

## Будущие Интеграции

Интеграции должны быть тонкими:

```text
Discord adapter
  -> convert Discord event to ModerationRequest
  -> call moderation core
  -> apply platform-specific action

Telegram adapter
  -> convert Telegram update to ModerationRequest
  -> call moderation core
  -> apply platform-specific action
```

Core должен оставаться стабильным, даже если платформенные адаптеры меняются.

## Production Policy And Action Layer

Policies can now be loaded from PostgreSQL through `policy_records`, with YAML kept as the safe fallback source. The resolver reads enabled records for the requested policy type and applies scope priority from most specific to least specific:

```text
USER
  -> ROLE
  -> CHANNEL
  -> GUILD / CHAT
  -> PLATFORM
  -> GLOBAL
  -> YAML fallback
```

Supported policy types are `PREPROCESSING`, `MODERATION_RULE`, `DECISION`, and `ACTION`. DB payloads are validated through the same Pydantic contracts as YAML policies; invalid payloads fail explicitly and are not silently accepted. If PostgreSQL is unavailable, the resolver logs the failure and falls back to the configured YAML loader when that is safe.

Action execution is separated from decision making. `DecisionEngine` only returns `ModerationDecision` with `decision_action` and `action_plan`; it does not know about Discord, Telegram, or any platform API. `ActionExecutor` consumes `ModerationDecision.action_plan.actions`, checks `ActionPolicy`, and executes each planned action through a `PlatformActionClient`.

`ActionPolicy` is configured in `configs/rules/action_policy.yaml` and is DB-ready via the `ACTION` policy type. It controls:

- `enabled` and `dry_run`
- allowed actions
- destructive actions
- actions that require manual review
- per-action timeouts
- retry policy
- platform overrides

In dry-run mode the executor returns `DRY_RUN` steps and does not call the real platform client. In active mode it executes actions in order, logs every step, skips forbidden actions, routes review-gated actions such as `BAN` to `REVIEW`/`SKIPPED`, and returns `SUCCESS`, `FAILED`, `SKIPPED`, or `PARTIAL_SUCCESS` for the whole plan. Execution steps are auditable through `action_execution_logs`.

