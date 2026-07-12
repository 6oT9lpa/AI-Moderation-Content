from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import snapshot_download


# Sources already present are checked and skipped.  Conversations is omitted:
# its CC-BY-NC licence is not suitable for an unknown/commercial bot deployment.
CACHE_TARGETS = (
    "Mnwa/russian-toxic",
    "textdetox/multilingual_paradetox",
    "redmadrobot-rnd/nsfw_benchmark",
    "Den4ikAI/russian_dialogues",
    "EustassKidman/malicious-url",
    "Abdurohman/fraudlens-ru-v1",
    "NiGuLa/Russian_Sensitive_Topics",
    "igorktech/tiny_conversations",
)


def _directory_name(dataset_id: str) -> str:
    return dataset_id.replace("/", "_")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download enabled Hugging Face sources into data/raw/hf.")
    parser.add_argument("--cache-dir", default="data/raw/hf")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--force", action="store_true", help="Re-download snapshots already present.")
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "datasets": {},
        "skipped": {
            "inkoziev/Conversations": "CC-BY-NC: do not cache or train for an unknown/commercial deployment",
        },
    }

    for dataset_id in CACHE_TARGETS:
        destination = cache_dir / _directory_name(dataset_id)
        if destination.exists() and any(destination.iterdir()) and not args.force:
            print(f"[cache] dataset={dataset_id} status=already_present path={destination}", flush=True)
            manifest["datasets"][dataset_id] = {"status": "already_present", "path": str(destination)}
            continue

        print(f"[cache] dataset={dataset_id} status=downloading", flush=True)
        try:
            snapshot_download(
                repo_id=dataset_id,
                repo_type="dataset",
                local_dir=destination,
                max_workers=max(1, args.workers),
            )
            size_bytes = sum(path.stat().st_size for path in destination.rglob("*") if path.is_file())
            print(f"[cache] dataset={dataset_id} status=complete bytes={size_bytes}", flush=True)
            manifest["datasets"][dataset_id] = {
                "status": "complete",
                "path": str(destination),
                "bytes": size_bytes,
            }
        except Exception as exc:
            print(f"[cache] dataset={dataset_id} status=error error={exc}", flush=True)
            manifest["datasets"][dataset_id] = {"status": "error", "error": str(exc), "path": str(destination)}

    (cache_dir / "cache_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
