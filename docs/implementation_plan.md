# Implementation plan

Документ фиксирует порядок реализации, чтобы не начинать с ML и не усложнять проект раньше времени.

## Этап 1. База проекта

1. Зафиксировать структуру директорий.
2. Добавить Pydantic V2 schemas.
3. Добавить domain enums и value objects.
4. Добавить application ports.
5. Добавить structured logger.
6. Добавить database layer и миграции.

## Этап 2. Dataset Collector

1. Создать `ai_message_events`.
2. Сохранять входящее событие до анализа.
3. Сохранять результат каждого этапа pipeline.
4. Добавить privacy sanitizer.
5. Подготовить dataset export query.

## Этап 3. Preprocessing и rules

1. Нормализация текста.
2. Извлечение features.
3. Hard rules.
4. Soft signals.
5. RuleResult с evidence и reason.

## Этап 4. Risk и decision

1. Risk score от `0` до `100`.
2. Risk breakdown.
3. Decision Engine.
4. Dry-run mode.
5. Human review routing.

## Этап 5. ML

1. Training export.
2. ruBERT baseline.
3. Evaluation.
4. False positive report.
5. Fallback только для спорных случаев.

## Definition of Done для MVP

- pipeline работает без ML;
- каждый этап логируется;
- dataset collector сохраняет audit trail;
- decision имеет reason code;
- training export можно собрать отдельно;
- автоматические действия включаются только после shadow mode.
