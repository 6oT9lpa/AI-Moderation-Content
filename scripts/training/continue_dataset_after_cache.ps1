param(
    [Parameter(Mandatory = $true)]
    [int]$CacheProcessId
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$cacheManifest = Join-Path $root 'data\raw\hf\cache_manifest.json'
$statusLog = Join-Path $root 'data\exports\rubert_moderation_v2_resume.log'
$buildOut = Join-Path $root 'data\exports\rubert_moderation_v2_build.stdout.log'
$buildErr = Join-Path $root 'data\exports\rubert_moderation_v2_build.stderr.log'

if (Get-Process -Id $CacheProcessId -ErrorAction SilentlyContinue) {
    Wait-Process -Id $CacheProcessId
}

if (-not (Test-Path -LiteralPath $cacheManifest)) {
    "[$(Get-Date -Format o)] cache manifest missing; build not started" | Add-Content -LiteralPath $statusLog
    exit 1
}

$manifest = Get-Content -LiteralPath $cacheManifest -Raw | ConvertFrom-Json
$failed = @($manifest.datasets.psobject.Properties | Where-Object { $_.Value.status -eq 'error' })
if ($failed.Count -gt 0) {
    "[$(Get-Date -Format o)] cache errors: $($failed.Name -join ', '); build not started" | Add-Content -LiteralPath $statusLog
    exit 1
}

"[$(Get-Date -Format o)] cache complete; starting dataset build" | Add-Content -LiteralPath $statusLog
Start-Process -FilePath (Join-Path $root '.venv\Scripts\python.exe') `
    -ArgumentList 'scripts/training/build_rubert_dataset.py', '--config', 'configs/training/dataset_mix_v1.yaml' `
    -WorkingDirectory $root `
    -RedirectStandardOutput $buildOut `
    -RedirectStandardError $buildErr `
    -WindowStyle Hidden
