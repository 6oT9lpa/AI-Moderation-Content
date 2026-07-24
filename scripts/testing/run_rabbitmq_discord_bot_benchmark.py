from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.modules.load_testing.rabbitmq_discord_bot_load_test_runner import (
    RabbitMqDiscordBotLoadTestConfig,
    RabbitMqDiscordBotLoadTestRunner,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark synthetic Discord bot events through RabbitMQ moderation workers.")
    parser.add_argument("--rabbitmq-url", default=os.environ.get("RABBITMQ_URL", "amqp://guest:guest@127.0.0.1:5672/%2F"))
    parser.add_argument("--task-queue", default=os.environ.get("RABBITMQ_TASK_QUEUE", "ai_moder.moderation.tasks"))
    parser.add_argument("--result-queue", default=os.environ.get("RABBITMQ_RESULT_QUEUE", "ai_moder.moderation.results"))
    parser.add_argument("--rps", default="20,50,100,200")
    parser.add_argument("--duration-seconds", type=float, default=60.0)
    parser.add_argument("--warmup-seconds", type=float, default=120.0)
    parser.add_argument("--warmup-rps", type=float, default=20.0)
    parser.add_argument("--pause-seconds", type=float, default=30.0)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--channels", type=int, default=200)
    parser.add_argument("--users-per-rps", type=int, default=12)
    parser.add_argument("--result-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


async def run() -> int:
    args = parse_args()
    rps_values = tuple(float(item.strip()) for item in args.rps.split(",") if item.strip())
    output: dict[str, Any] = {
        "config": {
            "rabbitmq_url": _redact_amqp_url(args.rabbitmq_url),
            "task_queue": args.task_queue,
            "result_queue": args.result_queue,
            "rps": rps_values,
            "duration_seconds": args.duration_seconds,
            "warmup_seconds": args.warmup_seconds,
            "warmup_rps": args.warmup_rps,
            "pause_seconds": args.pause_seconds,
            "repeats": args.repeats,
            "channels": args.channels,
            "users_per_rps": args.users_per_rps,
            "result_timeout_seconds": args.result_timeout_seconds,
        },
        "warmup": None,
        "benchmarks": {},
    }

    if args.warmup_seconds > 0 and args.warmup_rps > 0:
        print(f"=== rabbitmq warmup {args.warmup_rps:g} RPS for {args.warmup_seconds:g}s ===", flush=True)
        output["warmup"] = await _run_single(args, args.warmup_rps, args.warmup_seconds)
        print(json.dumps(output["warmup"], ensure_ascii=False, indent=2), flush=True)
        await asyncio.sleep(args.pause_seconds)

    for repeat in range(1, args.repeats + 1):
        print(f"=== rabbitmq benchmark repeat {repeat}/{args.repeats} ===", flush=True)
        for rps in rps_values:
            key = _rps_key(rps)
            print(f"=== rabbitmq {key} run {repeat} ===", flush=True)
            result = await _run_single(args, rps, args.duration_seconds)
            output["benchmarks"].setdefault(key, {"runs": []})["runs"].append({"run": repeat, **result})
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
            if args.pause_seconds > 0 and not (repeat == args.repeats and rps == rps_values[-1]):
                await asyncio.sleep(args.pause_seconds)

    for key, section in output["benchmarks"].items():
        section["median"] = _median_summary(section["runs"])

    print("=== rabbitmq summary ===", flush=True)
    print(json.dumps(output, ensure_ascii=False, indent=2), flush=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = [
        key
        for key, section in output["benchmarks"].items()
        if any(not run["targets_met"] for run in section["runs"])
    ]
    return 1 if failed else 0


async def _run_single(args: argparse.Namespace, rps: float, duration_seconds: float) -> dict[str, Any]:
    config = RabbitMqDiscordBotLoadTestConfig(
        rabbitmq_url=args.rabbitmq_url,
        task_queue=args.task_queue,
        result_queue=args.result_queue,
        total_messages=max(1, round(rps * duration_seconds)),
        duration_seconds=duration_seconds,
        channel_count=args.channels,
        user_count=max(1, int(rps * args.users_per_rps)),
        result_timeout_seconds=args.result_timeout_seconds,
    )
    return await RabbitMqDiscordBotLoadTestRunner(config).run()


def _median_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "moderation_success_rate": statistics.median(run["moderation_success_rate"] for run in runs),
        "achieved_end_to_end_messages_per_second": statistics.median(run["achieved_end_to_end_messages_per_second"] for run in runs),
        "end_to_end_latency": _median_latency(runs, "end_to_end_latency"),
        "moderation_latency": _median_latency(runs, "moderation_latency"),
    }


def _median_latency(runs: list[dict[str, Any]], field: str) -> dict[str, float]:
    keys = ("mean_ms", "p50_ms", "p80_ms", "p95_ms", "p99_ms")
    return {key: statistics.median(float(run[field][key]) for run in runs) for key in keys}


def _rps_key(rps: float) -> str:
    return f"{int(rps) if rps.is_integer() else rps:g}rps"


def _redact_amqp_url(value: str) -> str:
    if "@" not in value or "://" not in value:
        return value
    scheme, rest = value.split("://", 1)
    return f"{scheme}://***@{rest.split('@', 1)[1]}"


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
