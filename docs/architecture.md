# Архитектура AI Moderation Content

Проект является платформенно-независимым ядром ИИ-модерации. Он не должен зависеть от Discord, Telegram или будущего HTTP API. Внешние платформы подключаются через тонкие адаптеры, которые преобразуют события в общий `ModerationRequest` и применяют итоговый `ModerationResult`.

## Цель

Целевая форма на старте — clean modular monolith. Это один репозиторий с понятными слоями, без лишней enterprise-сложности.

## Pipeline

```text
Platform event
  -> ModerationRequest
  -> Text Preprocessor
  -> Media Analyzer
  -> Rule Engine
  -> Risk Scorer
  -> AI Classifier, optional
  -> Fallback, rare
  -> Decision Engine
  -> Dataset Collector
  -> ModerationResult
```

## Слои

### contracts

Pydantic V2 schemas для входов, выходов, конфигов, результатов этапов и dataset records.

### domain

Чистая предметная область: labels, actions, severity, rule match, risk score, moderation decision. Этот слой не импортирует БД, Pydantic, OCR, ML-библиотеки или platform SDK.

### application

Use cases, pipeline и ports. Application-слой управляет процессом, но не знает конкретную реализацию БД, OCR, очереди или модели.

### modules

Основной код модератора: preprocessing, media analysis, rule engine, risk scoring, decision engine, dataset collection, user history.

### infrastructure

Конкретные реализации: database, repositories, logging, queue, OCR, hashing, storage.

### training

Offline-код для подготовки датасета, обучения и evaluation. Он не должен попадать в hot path модерации.

### shared

Только реально переиспользуемые утилиты, exceptions и type aliases.

## Правила

1. Один класс — один файл.
2. Один файл — одна ответственность.
3. Каждый этап pipeline логирует start, success, failure, latency и reason code.
4. Domain не зависит от infrastructure.
5. Application работает через interfaces.
6. Infrastructure реализует interfaces.
7. Training отделён от online moderation.
8. Не создавать пустые классы заранее.
9. Не оставлять неиспользуемые функции и переменные.
