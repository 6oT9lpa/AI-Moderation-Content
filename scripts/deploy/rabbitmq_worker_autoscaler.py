from __future__ import annotations

import argparse
import json
import subprocess
import time
import base64
import urllib.parse
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scale RabbitMQ moderation workers for benchmark runs.")
    parser.add_argument("--rabbitmq-api-url", default="http://guest:guest@127.0.0.1:15672")
    parser.add_argument("--queue", default="ai_moder.moderation.tasks")
    parser.add_argument("--compose-file", default="docker-compose.rabbitmq-benchmark.yml")
    parser.add_argument("--service", default="moderation-worker")
    parser.add_argument("--min-workers", type=int, default=1)
    parser.add_argument("--mid-workers", type=int, default=2)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--low-queue-threshold", type=int, default=100)
    parser.add_argument("--high-queue-threshold", type=int, default=1000)
    parser.add_argument("--oldest-age-scale-up-seconds", type=float, default=5.0)
    parser.add_argument("--gpu-memory-scale-up-limit", type=float, default=85.0)
    parser.add_argument("--p95-scale-up-limit-ms", type=float, default=5_000.0)
    parser.add_argument("--metrics-path", type=Path, default=Path("/tmp/ai-moder-rabbitmq-worker-metrics.jsonl"))
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    history: deque[float] = deque(maxlen=6)
    while True:
        snapshot = _queue_snapshot(args.rabbitmq_api_url, args.queue)
        gpu_memory_pct = _gpu_memory_pct()
        p95_ms = _recent_p95(args.metrics_path)
        target = _target_workers(args, snapshot, gpu_memory_pct, p95_ms, history)
        _scale(args.compose_file, args.service, target)
        print(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "queue_messages": snapshot["messages"],
                    "queue_oldest_age_seconds": snapshot["oldest_age_seconds"],
                    "gpu_memory_pct": gpu_memory_pct,
                    "recent_worker_p95_ms": p95_ms,
                    "target_workers": target,
                    "scale_up_blocked_by_gpu": gpu_memory_pct is not None and gpu_memory_pct >= args.gpu_memory_scale_up_limit,
                    "scale_up_blocked_by_p95": p95_ms is not None and p95_ms >= args.p95_scale_up_limit_ms,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        if args.once:
            return 0
        time.sleep(args.interval_seconds)


def _queue_snapshot(api_url: str, queue: str) -> dict[str, Any]:
    encoded_queue = urllib.parse.quote(queue, safe="")
    parsed = urllib.parse.urlsplit(api_url.rstrip("/"))
    username = parsed.username
    password = parsed.password
    host = parsed.hostname or "127.0.0.1"
    netloc = host if parsed.port is None else f"{host}:{parsed.port}"
    base_url = urllib.parse.urlunsplit((parsed.scheme or "http", netloc, parsed.path, "", ""))
    url = f"{base_url.rstrip('/')}/api/queues/%2F/{encoded_queue}"
    request = urllib.request.Request(url)
    if username is not None and password is not None:
        token = base64.b64encode(f"{urllib.parse.unquote(username)}:{urllib.parse.unquote(password)}".encode("utf-8")).decode("ascii")
        request.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"messages": 0, "oldest_age_seconds": 0.0}
        raise
    oldest_age = 0.0
    message_stats = data.get("message_stats") or {}
    if data.get("messages", 0) > 0 and message_stats.get("publish_details", {}).get("rate", 0) == 0:
        oldest_age = float(data.get("idle_since") is not None) * 999.0
    return {"messages": int(data.get("messages", 0)), "oldest_age_seconds": oldest_age}


def _gpu_memory_pct() -> float | None:
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except Exception:
        return None
    rows = [line.strip() for line in output.splitlines() if line.strip()]
    if not rows:
        return None
    percentages = []
    for row in rows:
        used_raw, total_raw = [item.strip() for item in row.split(",", 1)]
        used = float(used_raw)
        total = float(total_raw)
        if total > 0:
            percentages.append(used / total * 100)
    return max(percentages) if percentages else None


def _recent_p95(metrics_path: Path) -> float | None:
    if not metrics_path.exists():
        return None
    lines = metrics_path.read_text(encoding="utf-8").splitlines()[-200:]
    values = []
    for line in lines:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("ok") and "duration_ms" in data:
            values.append(float(data["duration_ms"]))
    if len(values) < 5:
        return None
    values.sort()
    index = int(round((len(values) - 1) * 0.95))
    return values[index]


def _target_workers(args: argparse.Namespace, snapshot: dict[str, Any], gpu_memory_pct: float | None, p95_ms: float | None, history: deque[float]) -> int:
    queue_messages = int(snapshot["messages"])
    oldest_age = float(snapshot["oldest_age_seconds"])
    if queue_messages < args.low_queue_threshold:
        target = args.min_workers
    elif queue_messages <= args.high_queue_threshold:
        target = args.mid_workers
    else:
        target = args.max_workers
    if oldest_age > args.oldest_age_scale_up_seconds:
        target = args.max_workers

    history.append(p95_ms or 0.0)
    p95_rising = len(history) >= 3 and history[-1] > median(list(history)[:-1]) * 1.25 and history[-1] > 0
    scale_up_blocked = (
        (gpu_memory_pct is not None and gpu_memory_pct >= args.gpu_memory_scale_up_limit)
        or (p95_ms is not None and p95_ms >= args.p95_scale_up_limit_ms)
        or p95_rising
    )
    if scale_up_blocked:
        return min(target, args.mid_workers)
    return target


def _scale(compose_file: str, service: str, workers: int) -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            "ai-moder",
            "-f",
            compose_file,
            "up",
            "-d",
            "--no-deps",
            "--scale",
            f"{service}={workers}",
            service,
        ],
        check=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())
