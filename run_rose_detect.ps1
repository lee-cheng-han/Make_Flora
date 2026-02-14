# Launch rose detection webcam (ESP32-CAM stream + AI)
# Double-click or run: .\run_rose_detect.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# ESP32-CAM stream URL (change if your camera has a different IP)
$env:CAMERA_SOURCE = "http://172.19.129.149/stream"

Write-Host "Installing dependencies (if needed)..." -ForegroundColor Cyan
pip install opencv-python ultralytics --quiet

Write-Host "`nRoses and flowers - boxing from ESP32-CAM. Press q to quit.`n" -ForegroundColor Cyan
python webcam_rose_detect.py
