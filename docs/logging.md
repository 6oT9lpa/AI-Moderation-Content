# Logging

В проекте используется structured logging. Все действия pipeline должны быть видны в логах и связаны через `correlation_id`.

## Обязательные поля

Каждая запись лога должна содержать:

- `timestamp`;
- `level`;
- `correlation_id`;
- `stage`;
- `event_id`, если он уже создан;
- `message_id`, если доступен;
- `duration_ms`, если этап завершён;
- `status`: `start`, `success`, `failure`;
- `reason_code`, если есть решение или ошибка.

## Что логировать

Логируются:

- получение moderation request;
- запуск и завершение каждого этапа pipeline;
- результат preprocessing;
- результат media analysis;
- rule matches;
- risk score и risk breakdown;
- classifier/fallback result;
- decision engine result;
- dataset write;
- ошибки БД, OCR, очереди и модели.

## Что не логировать

Не нужно писать в логи секреты, токены, приватные ссылки, email, телефоны и полный raw text без необходимости. Для долгого хранения использовать masked/anonymized версии.

## Уровни

- `DEBUG` — подробности локальной диагностики.
- `INFO` — нормальный проход pipeline.
- `WARNING` — спорный результат, fallback, review, retry.
- `ERROR` — ошибка этапа без падения процесса.
- `CRITICAL` — ошибка, из-за которой сервис не может продолжать работу.

## Принцип

Лог должен отвечать на вопрос: что произошло, на каком этапе, сколько заняло времени, какое решение было принято и почему.
