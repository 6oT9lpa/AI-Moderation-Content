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

## Architecture

```text
Platform event
  -> normalized API request
  -> text preprocessing
  -> preprocessing rule signals
  -> ruBERT classifier
  -> moderation rule engine
  -> decision engine
  -> action policy / executor
  -> API response and audit-ready payload
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
