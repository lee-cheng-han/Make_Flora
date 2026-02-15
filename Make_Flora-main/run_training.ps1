# Install dependencies then run YOLO11 training.
# Run in PowerShell: .\run_training.ps1
# Or: python train_yolo11_roboflow.py  (after pip install -r requirements-train.txt once)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Installing dependencies (roboflow, ultralytics)..." -ForegroundColor Cyan
if (Test-Path "requirements-train.txt") { pip install -r requirements-train.txt } else { pip install roboflow ultralytics }
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`nStarting training..." -ForegroundColor Cyan
python train_yolo11_roboflow.py
exit $LASTEXITCODE
