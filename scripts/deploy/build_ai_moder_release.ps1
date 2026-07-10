param(
    [string]$Archive = (Join-Path $env:TEMP 'ai-moder-release.tar.gz')
)

$ErrorActionPreference = 'Stop'

if (Test-Path $Archive) {
    Remove-Item -LiteralPath $Archive
}

tar --exclude='./.git' `
    --exclude='./venv' `
    --exclude='./.venv' `
    --exclude='./activity/client/node_modules' `
    --exclude='./data' `
    --exclude='./logs' `
    --exclude='./.tmp' `
    --exclude='./.env' `
    --exclude='./__pycache__' `
    --exclude='./.pytest_cache' `
    --exclude='./htmlcov' `
    --exclude='./.coverage' `
    --exclude='./models' `
    --exclude='./data' `
    --exclude='./logs' `
    --exclude='./attachments' `
    --exclude='./.mypy_cache' `
    --exclude='./.ruff_cache' `
    --exclude='./ollama_models' `
    --exclude='./.ollama' `
    -czf $Archive .

Write-Host "AI moderator release archive created: $Archive"
