# Make_Flora – Roses & Flowers Detection

Detect roses and flowers from your webcam or ESP32-CAM stream using Roboflow workflows (find-roses + find-cluster-of-flowers).

## Setup on a New Computer

### 1. Clone the repo

```bash
git clone https://github.com/lee-cheng-han/Make_Flora.git
cd Make_Flora
```

### 2. Install Python dependencies

**Windows (PowerShell):**
```powershell
pip install -r requirements.txt
```

**Linux/Mac:**
```bash
pip install -r requirements.txt
```

### 3. Run detection

**Windows (PowerShell):**
```powershell
.\run_rose_detect.ps1
```

**Linux/Mac:**
```bash
python webcam_rose_detect.py
```

Uses built-in webcam by default. For ESP32-CAM:

```powershell
$env:CAMERA_SOURCE = "http://YOUR_ESP32_IP/stream"
.\run_rose_detect.ps1
```

## ESP32-CAM Setup

1. Open `ESP32_CAM_Stream/ESP32_CAM_Stream.ino` in Arduino IDE
2. Set your WiFi credentials (ssid, password)
3. Board: **AI Thinker ESP32-CAM**
4. Upload
5. Serial Monitor (115200) shows the IP – use `http://IP/stream` for the camera URL

## Training (Optional)

To train your own model on Roboflow data:

```powershell
.\run_training.ps1
```

Or `python train_yolo11_roboflow.py`. Requires a Roboflow project with a dataset version.

## Project Structure

- `webcam_rose_detect.py` – main detection script (Roboflow API or local best.pt)
- `run_rose_detect.ps1` – run detection (Windows)
- `run_training.ps1` – run training (Windows)
- `train_yolo11_roboflow.py` – YOLO11 training on Roboflow
- `ESP32_CAM_Stream/` – ESP32-CAM streaming sketch
- `ESP32-CAM_CameraWebServer/` – full CameraWebServer for ESP32-CAM
- `esp32cam_get_ip/` – WiFi diagnostic sketch
