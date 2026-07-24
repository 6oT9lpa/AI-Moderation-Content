from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.modules.load_testing.rabbitmq_moderation_worker import RabbitMqModerationWorker, RabbitMqModerationWorkerConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RabbitMQ moderation batch worker.")
    parser.add_argument("--rabbitmq-url", default=os.environ.get("RABBITMQ_URL", "amqp://guest:guest@127.0.0.1:5672/%2F"))
    parser.add_argument("--task-queue", default=os.environ.get("RABBITMQ_TASK_QUEUE", "ai_moder.moderation.tasks"))
    parser.add_argument("--result-queue", default=os.environ.get("RABBITMQ_RESULT_QUEUE", "ai_moder.moderation.results"))
    parser.add_argument("--batch-size", type=int, default=int(os.environ.get("RABBITMQ_WORKER_BATCH_SIZE", "32")))
    parser.add_argument("--batch-timeout-ms", type=int, default=int(os.environ.get("RABBITMQ_WORKER_BATCH_TIMEOUT_MS", "50")))
    parser.add_argument("--prefetch-count", type=int, default=int(os.environ.get("RABBITMQ_WORKER_PREFETCH", "128")))
    parser.add_argument("--worker-id", default=os.environ.get("RABBITMQ_WORKER_ID", ""))
    parser.add_argument("--metrics-path", default=os.environ.get("RABBITMQ_WORKER_METRICS_PATH"))
    parser.add_argument("--action-dry-run", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = RabbitMqModerationWorkerConfig(
        rabbitmq_url=args.rabbitmq_url,
        task_queue=args.task_queue,
        result_queue=args.result_queue,
        batch_size=args.batch_size,
        batch_timeout_ms=args.batch_timeout_ms,
        prefetch_count=args.prefetch_count,
        action_dry_run=args.action_dry_run,
        worker_id=args.worker_id or f"{socket.gethostname()}-{os.getpid()}",
        metrics_path=args.metrics_path,
    )
    RabbitMqModerationWorker(config).run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
