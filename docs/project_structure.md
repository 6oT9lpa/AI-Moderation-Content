# Структура проекта

Это MVP-структура. Она задаёт границы проекта, но не требует заранее создавать пустые классы.

```text
AI-Moderation-Content/
  configs/
  src/ai_moderation/
    contracts/
    domain/
    application/
    modules/
    infrastructure/
    training/
    shared/
  scripts/
  tests/
  docs/
  data/
  models/
  logs/
```

## Назначение папок

`contracts/` — Pydantic V2 schemas.

`domain/` — labels, actions, severity, rule match, risk score, decision.

`application/` — use cases, pipeline и ports/interfaces.

`modules/` — preprocessing, media analysis, rule engine, risk scoring, decision engine, dataset collection.

`infrastructure/` — database, repositories, logging, queue, OCR, hashing, storage.

`training/` — dataset build, training и evaluation.

`shared/` — общие utils, exceptions и type aliases.

## Правило добавления файлов

Новый файл добавляется только под конкретную задачу. Если появляется класс `RiskScorer`, файл называется `risk_scorer.py`. Если появляется `DatasetCollector`, файл называется `dataset_collector.py`.

## Границы

Domain не импортирует infrastructure. Application работает через interfaces. Infrastructure реализует interfaces. Training не попадает в hot path модерации.
