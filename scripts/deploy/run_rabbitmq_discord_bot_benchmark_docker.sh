#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ai-moder}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.rabbitmq-benchmark.yml}"
OUTPUT_DIR="${OUTPUT_DIR:-${APP_DIR}/logs/rabbitmq-benchmark}"
WORKER_SCALE_START="${WORKER_SCALE_START:-${RABBITMQ_AUTOSCALER_MIN_WORKERS:-1}}"
WORKER_READY_SECONDS="${WORKER_READY_SECONDS:-45}"

cd "$APP_DIR"
mkdir -p "$OUTPUT_DIR"
rm -f "$OUTPUT_DIR/worker_metrics.jsonl" "$OUTPUT_DIR/rabbitmq_discord_bot_benchmark_summary.json"

echo "compose_file=${COMPOSE_FILE}"
echo "output_dir=${OUTPUT_DIR}"

docker compose -f "$COMPOSE_FILE" build rabbitmq-loadtest moderation-worker autoscaler
docker compose -f "$COMPOSE_FILE" up -d rabbitmq

for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:15672/api/overview -u guest:guest >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

docker compose -f "$COMPOSE_FILE" up -d --scale "moderation-worker=${WORKER_SCALE_START}" moderation-worker
docker compose -f "$COMPOSE_FILE" up -d autoscaler

echo "waiting for worker metrics or logs"
sleep "$WORKER_READY_SECONDS"
docker compose -f "$COMPOSE_FILE" ps
docker compose -f "$COMPOSE_FILE" logs --tail=80 moderation-worker || true

set +e
docker compose -f "$COMPOSE_FILE" run --rm rabbitmq-loadtest
exit_code=$?
set -e

echo "=== benchmark summary ==="
if [ -f "$OUTPUT_DIR/rabbitmq_discord_bot_benchmark_summary.json" ]; then
  cat "$OUTPUT_DIR/rabbitmq_discord_bot_benchmark_summary.json"
else
  echo "summary file missing: $OUTPUT_DIR/rabbitmq_discord_bot_benchmark_summary.json" >&2
fi

echo "=== autoscaler tail ==="
docker compose -f "$COMPOSE_FILE" logs --tail=120 autoscaler || true

echo "=== worker tail ==="
docker compose -f "$COMPOSE_FILE" logs --tail=120 moderation-worker || true

exit "$exit_code"
