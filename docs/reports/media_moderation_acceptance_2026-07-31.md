# Media moderation acceptance report — 2026-07-31

## Verified locally

- AI-Moderator full suite: `1663 passed` (`python -m pytest -q`).
- OmniBot full Python suite: `216 passed, 41 skipped` with coverage disabled because the existing
  `.coverage` file was locked by another process.
- Activity: `16 passed` (`npm test -- --run`) and a successful `tsc && vite build`.
- ONNX Runtime `1.28.0` installed on Python 3.14; `pip check` reported no broken requirements.
- CPU runtime providers: `AzureExecutionProvider`, `CPUExecutionProvider`.
- Local GPU: NVIDIA GeForce RTX 4060 Laptop GPU, 8 GB. This is not the production GTX 1650.
- Alembic `0001_media_moderation_api:0002_media_policy_snapshots --sql` generated both
  `media_policy_snapshots` and `media_policy_audit` PostgreSQL tables and the revision update.
- Runtime searches found no `IMAGE_SCAM` in OmniBot. Its only AI-Moderator occurrences are negative
  tests that verify the value is rejected.
- A real PaddleOCR CPU smoke had previously completed with three Russian/English/URL lines,
  mean confidence `0.9693473`, and `1507 ms` latency using the verified local model bundle.

## Implemented commits

AI-Moderator:

- `703bf09` strict OCR and detector YAML defaults.
- `72f7a46`, `ee8b845` verified PaddleOCR v3 CPU runtime and Windows hardening.
- `965c1b1` versioned PostgreSQL media snapshots, audit, revision conflict and YAML fallback.
- `76dc2cd` verified MIT YOLO ONNX runtime and effective guild policy wiring.
- `54fa67a` pinned MIT training/export workflow.
- `2f7b49a` production-provider benchmark runner.
- `3c892f9` OCR policy filtering followed by shared preprocessing and Tiny2.
- `da4a0f7` Alembic psycopg 3 URL handling.

OmniBot:

- `161e3e9` Activity/backend media-policy save, reload, reset, conflict and unavailable flow.

## External acceptance still required

These checks were not represented as successful:

- Training cannot start because no object-detection images, annotations or dataset YAML are present.
- ONNX/TensorRT accuracy and latency cannot be measured because no trained detector artifact exists.
- GTX 1650 FP16/INT8 benchmarking requires that physical production GPU and an engine built on it.
- Online migration verification is blocked by the invalid local PostgreSQL credentials currently in
  `.env`; no database was modified.
- The real Discord Activity scenarios A–E require a deployed test environment, Discord session,
  test guild and explicit deployment authority. No deployment, push or remote-server mutation was
  performed.

When those prerequisites exist, use `scripts/training/train_mit_yolo.py`, package the exported model
with `scripts/training/package_yolo_onnx.py`, and retain the JSON result produced by
`python -m scripts.media.benchmark_onnx_yolo` with the release artifact.
