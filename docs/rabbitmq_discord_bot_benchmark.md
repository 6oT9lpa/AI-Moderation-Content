# RabbitMQ Discord bot moderation benchmark

Этот стенд проверяет не прямой HTTP-вызов `/moderation/messages`, а рабочий узел ближе к продакшену:

1. synthetic Discord bot публикует события в RabbitMQ;
2. moderation worker забирает сообщения пачками;
3. ruBERT классифицирует batch;
4. rule/decision engine считает `risk` и `action` для каждого сообщения;
5. worker публикует результат в result queue и пишет dry-run action callback в БД;
6. autoscaler меняет количество worker-контейнеров по глубине очереди и guardrail-метрикам.

## Правила autoscaler

- `queue < 100` → 1 worker;
- `queue 100–1000` → 2 workers;
- `queue > 1000` → до 4 workers;
- если backlog/oldest age больше 5 секунд → до 4 workers;
- если GPU memory >= 85% или свежий worker p95 >= 5000 ms / резко растёт → scale-up блокируется и фиксируется bottleneck.

## Запуск на deploy-сервере

```bash
cd /opt/ai-moder
bash scripts/deploy/run_rabbitmq_discord_bot_benchmark_docker.sh
```

Итоги пишутся сюда:

```text
/opt/ai-moder/logs/rabbitmq-benchmark/rabbitmq_discord_bot_benchmark_summary.json
/opt/ai-moder/logs/rabbitmq-benchmark/worker_metrics.jsonl
```

## Прогон 2026-07-24 на deploy-сервере

Конфигурация:

- warmup: 20 RPS, 120 секунд;
- тесты: 20, 50, 100, 200 RPS;
- каждый тест: 60 секунд;
- повторы: 3;
- пауза между тестами: 30 секунд;
- batch worker: 32;
- model: `/app/models/rubert-tiny2-moderation-trained`;
- ruBERT загрузился успешно, но на сервере Docker запустил worker на CPU, потому что NVIDIA runtime для контейнеров не настроен.

Warmup прошёл без потерь: `2400/2400`, p95 end-to-end `39.017 ms`.

Медиана по 3 прогонам:

| RPS | runs | received | max missing | success | e2e RPS | e2e p50 ms | e2e p80 ms | e2e p95 ms | e2e p99 ms | moderation p95 ms | moderation p99 ms |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 3 | 3,600 | 0 | 1.000 | 19.904 | 26.861 | 32.143 | 48.138 | 65.051 | 36.000 | 48.040 |
| 50 | 3 | 9,000 | 0 | 1.000 | 49.341 | 38.285 | 57.097 | 102.492 | 144.156 | 56.000 | 78.000 |
| 100 | 3 | 18,000 | 0 | 1.000 | 91.841 | 5,620.828 | 6,062.954 | 6,571.131 | 6,760.087 | 566.000 | 621.000 |
| 200 | 3 | 36,000 | 0 | 1.000 | 140.009 | 19,384.441 | 23,048.993 | 25,149.257 | 25,640.189 | 708.000 | 800.010 |

Вывод:

- RabbitMQ pipeline не потерял сообщения ни на одном уровне нагрузки.
- 20–50 RPS проходят комфортно даже на CPU.
- На 100 RPS очередь начинает накапливаться: moderation latency ещё меньше секунды, но end-to-end p95 уже около 6.6 секунд.
- На 200 RPS очередь становится главным источником задержки: end-to-end p95 около 25 секунд.
- Autoscaler сработал: на 100 RPS поднимал `target_workers=2`, на 200 RPS поднимал `target_workers=4`, затем снижал обратно при разгрузке очереди.

## Важное про GPU

Worker запускается отдельным контейнером. Для CUDA внутри контейнера на сервере нужен NVIDIA Container Toolkit. Compose не требует GPU жёстко: если NVIDIA runtime не настроен, worker стартует на CPU, а autoscaler показывает `gpu_memory_pct=null`.

Такой прогон полезен как bottleneck-тест очереди/CPU, но не заменяет GPU batch benchmark. После установки NVIDIA Container Toolkit нужно повторить тот же сценарий: ожидаемо 100/200 RPS должны стать сильно лучше по end-to-end задержке.
