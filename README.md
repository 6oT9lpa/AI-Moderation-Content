# AI Moderator

AI Moderator is a local moderation engine and HTTP API for community platforms.
It is currently used by OmniBot to analyze selected Discord channels through a
self-hosted API.

The project is platform-independent at the core: Discord, Telegram, dashboards,
and future adapters should send normalized requests to the API or application
services instead of coupling directly to the moderation pipeline.

## Current Status

Ready components:

- FastAPI moderation API;
- PostgreSQL-backed policy repository with YAML fallback;
- preprocessing rules for URLs, invites, spam, flood, evasion, semantic hate,
  and NSFW signals;
- ruBERT tiny2 moderation classifier loading from
  `models/rubert-tiny2-moderation-trained`;
- CUDA inference when NVIDIA drivers and CUDA-ready PyTorch are available;
- moderation rule engine with risk scoring and conflict handling;
- decision engine with action bundles;
- action policy and dry-run capable action executor;
- health endpoint that reports database, policy, and ruBERT readiness;
- deployment scripts for `/opt/ai-moder`;
- training, evaluation, and model utility scripts;
- load-testing module and local testing script.

The API can run without a GPU, but GPU inference is preferred when available.
The production server currently loads the trained ruBERT model on CUDA when the
NVIDIA driver is installed and PyTorch reports `cuda_available=True`.

## Training Results

The current moderation dataset contains 1,049,399 examples with a
`735,000 / 157,202 / 157,197` train, validation, and test split. The ruBERT
model was trained on the 735,000-example training split. The selected checkpoint
is epoch 4 (`checkpoint-183752`) with validation micro-F1 `0.9298`, macro-F1
`0.8381`, and exact match `0.8610`. The final held-out test result is micro-F1
`0.9358` and macro-F1 `0.8396`.

![Training overview](./docs/images/training/training_overview.png)

The loss curve shows the training trajectory and the best validation-loss point.
The final training epoch is retained for comparison, while the best checkpoint
is selected separately from the final checkpoint.

![Training and validation loss](./docs/images/training/loss_by_step.png)

Validation metrics make it possible to compare micro-F1, macro-F1, and exact
match across epochs and identify the checkpoint selected for deployment.

![Validation metrics by epoch](./docs/images/training/validation_metrics_by_epoch.png)

The learning-rate chart documents warmup and decay, which is useful when
comparing runs with different training schedules.

![Learning rate by step](./docs/images/training/learning_rate_by_step.png)

Per-label precision, recall, and F1 expose uneven model quality that aggregate
metrics can hide. `TOXIC` has the lowest recall among labels with meaningful
held-out support (`0.7816`) and remains a priority for additional hard examples.
`FLOOD` has only one held-out example and `IMAGE_SCAM` has none, so these labels
must remain primarily rule-engine driven until representative test coverage is
added.

![Test quality by moderation label](./docs/images/training/test_per_label_metrics.png)

Target-versus-predicted positive counts make threshold and calibration bias
visible for each label.

![Test target versus predicted label balance](./docs/images/training/test_prediction_balance.png)

The training corpus is intentionally multi-label, so label totals can exceed the
number of rows. The chart below is useful for identifying underrepresented
classes before the next training run.

![Training dataset label distribution](./docs/images/training/label_distribution.png)

The source distribution chart documents how public, synthetic, and moderated
project examples contribute to the assembled dataset.

![Training dataset source distribution](./docs/images/training/source_distribution.png)

Regenerate the local report after a training run:

```powershell
.\.venv\Scripts\python.exe scripts\training\build_rubert_training_report.py
```

Use `--include-test-evaluation` to rerun inference over the test split and
refresh per-label metrics.

## Training Workflow

```mermaid
flowchart LR
    A[Public and project data] --> B[Sanitization and relabeling]
    B --> C[Dataset split]
    C --> D[ruBERT training]
    D --> E[Validation threshold calibration]
    E --> F[Test and hard-pack evaluation]
    F --> G[Training report and charts]
    G --> H[Local moderation model]
```

## Architecture

```mermaid
flowchart LR
    A[Discord or platform adapter] --> B[Local FastAPI API]
    B --> C[Text preprocessing]
    C --> D[Preprocessing rules]
    C --> E[ruBERT classifier]
    D --> F[Moderation rule engine]
    E --> F
    F --> G[Risk score]
    G --> H[Decision engine]
    H --> I[Action policy and executor]
    H --> J[Dataset collector]
    I --> K[API response]
    J --> L[PostgreSQL training feedback]
```

Core principles:

- one class per file where practical;
- platform adapters stay thin;
- rules and policies are data-driven;
- destructive actions are policy-gated;
- model output is explainable through labels, scores, reasons, and evidence;
- logs are written for important service, policy, model, and request events;
- the engine assists moderators and does not replace human governance.

## API

Main local service:

```text
uvicorn main_api:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Important endpoints:

- `GET /health` - database, policy, and model readiness;
- `POST /moderation/messages` - analyze a platform message;
- `GET /api/policies/effective` - inspect effective policies.

The API should be protected by an internal API key and network boundary. In the
OmniBot deployment it listens on localhost and is called by the Discord bot
backend.

## Configuration

Example:

```env
DATABASE_URL=postgresql://ai_moder:change_me@127.0.0.1:5432/ai_moder
API_HOST=127.0.0.1
API_PORT=8000
API_KEY=change_me
API_RUBERT_REQUIRED=true
API_RUBERT_MODEL_DIR=models/rubert-tiny2-moderation-trained
LOG_LEVEL=INFO
```

Model artifacts are intentionally not packed into release archives by default.
Deploy the trained model separately into:

```text
/opt/ai-moder/models/rubert-tiny2-moderation-trained
```

## Deployment

Build a release archive without secrets, logs, virtual environments, runtime
data, and model artifacts:

```powershell
scripts/deploy/build_ai_moder_release.ps1
```

Upload and deploy to the local server:

```powershell
scripts/deploy/deploy_ai_moder_local.ps1 `
  -SshPassword $env:AI_MODER_SSH_PASSWORD `
  -RootPassword $env:AI_MODER_ROOT_PASSWORD
```

Production directory:

```text
/opt/ai-moder
```

Systemd service:

```bash
sudo systemctl enable ai-moder.service
sudo systemctl restart ai-moder.service
sudo systemctl status ai-moder.service
```

GPU check:

```bash
nvidia-smi
/opt/ai-moder/.venv/bin/python - <<'PY'
import torch
print(torch.cuda.is_available())
print(torch.cuda.device_count())
print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu")
PY
```

## Testing

```bash
python -m pytest
```

Targeted examples:

```bash
python -m pytest tests/modules/preprocessing tests/presentation/api
python scripts/testing/run_moderation_load_test.py --base-url http://127.0.0.1:8000
```

## Data And Privacy

AI Moderator may process message text, platform IDs, policy metadata, labels,
risk scores, confidence values, and technical logs. See:

- [Privacy Policy](./docs/PRIVACY_POLICY.md)
- [Terms of Service / Acceptable Use](./docs/TERMS_OF_SERVICE.md)

## License

This project is proprietary commercial software. It is not open source.

No production use, commercial use, copying, modification, redistribution,
hosting, resale, white-label use, or SaaS use is granted unless a separate
written commercial license or contract explicitly allows it.

See:

- [LICENSE](./LICENSE)
- [Commercial License Terms](./COMMERCIAL_LICENSE.md)
