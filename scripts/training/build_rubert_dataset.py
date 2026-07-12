from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.training.datasets.moderation_dataset_assembler import ModerationDatasetAssembler
from src.training.datasets.moderation_dataset_mix_config import ModerationDatasetMixConfig


def _apply_cpu_affinity(cpu_limit_percent: int) -> int:
    """Reserve part of the machine for the bot and OS during a large build."""
    cpu_count = os.cpu_count() or 1
    allowed_cpus = max(1, min(cpu_count, int(cpu_count * cpu_limit_percent / 100)))

    if sys.platform == "win32":
        import ctypes

        mask = (1 << allowed_cpus) - 1
        result = ctypes.windll.kernel32.SetProcessAffinityMask(
            ctypes.windll.kernel32.GetCurrentProcess(), ctypes.c_size_t(mask)
        )
        if not result:
            # Some Windows app containers disallow changing process affinity.
            # Building must still work there; the worker setting remains active.
            return 0
    elif hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, set(range(allowed_cpus)))

    return allowed_cpus


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ruBERT moderation dataset JSONL splits.")
    parser.add_argument("--config", default="configs/training/dataset_mix_v1.yaml")
    parser.add_argument(
        "--allow-shortfall",
        action="store_true",
        help="Write available rows and manifest instead of failing when source quotas are not satisfied.",
    )
    args = parser.parse_args()

    config = ModerationDatasetMixConfig.load(args.config)
    allowed_cpus = _apply_cpu_affinity(config.dataset.cpu_limit_percent)
    affinity_status = allowed_cpus if allowed_cpus else "unavailable"
    print(
        f"[dataset] runtime workers={config.dataset.workers} cpu_limit={config.dataset.cpu_limit_percent}% "
        f"affinity_cpus={affinity_status}",
        flush=True,
    )
    manifest = ModerationDatasetAssembler(config).build(strict=not args.allow_shortfall)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
