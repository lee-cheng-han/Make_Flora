# Launch rose detection webcam
# Double-click or run: .\run_rose_detect.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Installing dependencies (if needed)..." -ForegroundColor Cyan
pip install opencv-python ultralytics --quiet

Write-Host "`nStarting webcam rose detection..." -ForegroundColor Cyan
Write-Host "Point at a rose. Press 'q' to quit.`n" -ForegroundColor Yellow
python webcam_rose_detect.py
