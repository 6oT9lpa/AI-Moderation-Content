param([Parameter(Mandatory = $true)][int]$BuildProcessId)

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $root
if (Get-Process -Id $BuildProcessId -ErrorAction SilentlyContinue) { Wait-Process -Id $BuildProcessId }
$manifest = Join-Path $root 'data\exports\rubert_moderation_v2\manifest.json'
if (-not (Test-Path -LiteralPath $manifest)) { exit 1 }
& (Join-Path $root '.venv\Scripts\python.exe') scripts/training/audit_rubert_dataset.py --dataset-dir data/exports/rubert_moderation_v2 --apply *>> (Join-Path $root 'data\exports\rubert_moderation_v2_audit.log')
