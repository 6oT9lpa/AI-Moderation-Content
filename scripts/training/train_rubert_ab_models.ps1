$ErrorActionPreference = "Stop"

$Python = ".\.venv\Scripts\python.exe"
$Dataset = "data\exports\moderation_dataset_v2"
$TinySource = "models\rubert-tiny2-moderation-trained-20260729"
$TinyOutput = "models\rubert-tiny2-moderation-ab-20260730"
$DistilConfig = "configs\training\rubert_distil_conversational.yaml"
$DistilSource = "models\distilrubert-base-cased-conversational"
$DistilOutput = "models\distilrubert-base-cased-conversational-moderation-ab-20260730"
$LogDirectory = "data\reports\rubert_ab_training_20260730"

New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null

& $Python scripts\training\train_rubert_tiny2.py `
    --config configs\training\rubert_tiny2.yaml `
    --dataset-dir $Dataset `
    --model-source $TinySource `
    --output-dir $TinyOutput `
    --learning-rate 5e-6 `
    --epochs 2 2>&1 |
    Tee-Object -FilePath "$LogDirectory\tiny2.log"

if ($LASTEXITCODE -ne 0) {
    throw "Tiny2 training failed with exit code $LASTEXITCODE"
}

& $Python scripts\training\train_rubert_tiny2.py `
    --config $DistilConfig `
    --dataset-dir $Dataset `
    --model-source $DistilSource `
    --output-dir $DistilOutput 2>&1 |
    Tee-Object -FilePath "$LogDirectory\distilrubert.log"

if ($LASTEXITCODE -ne 0) {
    throw "DistilRuBERT training failed with exit code $LASTEXITCODE"
}

Write-Host "Both A/B models finished successfully." -ForegroundColor Green
