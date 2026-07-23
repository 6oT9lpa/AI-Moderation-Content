# Discord bot node benchmark

Этот benchmark запускает отдельный контейнер-генератор нагрузки, который эмулирует путь Discord bot worker:

```text
synthetic Discord MESSAGE_CREATE
  -> bot payload adapter
  -> POST /moderation/messages
  -> ruBERT / rules / decision engine на боевом API
  -> dry-run POST /actions/result для non-IGNORE действий
```

Контейнер не подключается к реальному Discord Gateway. Это сделано намеренно: Discord Gateway/rate limits внесли бы шум в RPS-замеры. Тест измеряет рабочий moderation node без внешних Discord-лимитов.

## Что проверяется

- формирование Discord-like payload;
- mention counts;
- attachment metadata;
- recent user messages;
- moderation API;
- ИИ-классификатор на деплое;
- decision engine;
- dry-run action result callback.

## Требования на сервере

Нужен Docker или совместимый runtime.

Проверка:

```bash
docker --version
```

На текущем сервере на момент подготовки benchmark Docker/Podman не установлен, поэтому контейнерный прогон требует установки runtime.

## Основной запуск

Скрипт:

```bash
scripts/deploy/run_discord_bot_node_benchmark_docker.sh
```

По умолчанию он делает:

```text
warmup: 120 sec at 20 RPS
benchmarks: 20, 50, 100, 200 RPS
repeats: 3
duration: 60 sec each
pause: 30 sec between runs
post action results: enabled, dry-run
```

Во время теста rate limit временно повышается до `20000/60s`, чтобы benchmark не измерял быстрые `429`. После завершения скрипт восстанавливает постоянный лимит:

```text
AI_MODERATOR_API_RATE_LIMIT=600
AI_MODERATOR_API_RATE_WINDOW_SECONDS=60
```

## Пример запуска на деплое

```bash
cd /opt/ai-moder
bash scripts/deploy/run_discord_bot_node_benchmark_docker.sh
```

Итоговые файлы пишутся в:

```text
/tmp/ai-moder-discord-bot-node-benchmark-YYYYMMDD_HHMMSS/
```

Основные файлы:

```text
benchmark.log
summary.json
env.backup
```

## Настраиваемые параметры

Пример:

```bash
RPS=20,50,100,200 \
REPEATS=3 \
DURATION_SECONDS=60 \
WARMUP_SECONDS=120 \
WARMUP_RPS=20 \
PAUSE_SECONDS=30 \
MAX_IN_FLIGHT=2000 \
bash scripts/deploy/run_discord_bot_node_benchmark_docker.sh
```

Можно отключить `/actions/result`, если нужно измерить только moderation endpoint:

```bash
POST_ACTION_RESULTS=false bash scripts/deploy/run_discord_bot_node_benchmark_docker.sh
```

## Локальный запуск без deploy wrapper

```bash
docker build -f Dockerfile.discord-bot-loadtest -t ai-moder-discord-bot-loadtest:local .

docker run --rm --network host \
  -e AI_MODERATOR_INTERNAL_API_KEY="$AI_MODERATOR_INTERNAL_API_KEY" \
  -e AI_MODERATOR_API_URL="http://127.0.0.1:8000" \
  -v /tmp/ai-moder-benchmark:/out \
  ai-moder-discord-bot-loadtest:local \
  --rps 20,50,100,200 \
  --warmup-seconds 120 \
  --warmup-rps 20 \
  --duration-seconds 60 \
  --repeats 3 \
  --pause-seconds 30 \
  --output /out/summary.json
```

## Почему отдельный контейнер

Отдельный контейнер нужен, чтобы:

- не смешивать нагрузочный генератор с API-процессом;
- не импортировать ruBERT/torch в генератор;
- чисто измерять API+классификатор на деплое;
- легко повторять тест;
- иметь отдельные логи и summary.

## Важное ограничение

Это synthetic Discord bot path, а не реальный Discord Gateway. Он проверяет рабочий moderation node, но не проверяет:

- реальные gateway reconnects;
- Discord API rate limits;
- реальные права бота;
- задержки Discord webhook/mod-log сообщений.

Для проверки реального Discord поведения нужен отдельный live smoke-test на тестовом сервере Discord.
