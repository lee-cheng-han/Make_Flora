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

## Web App (Boxes on Webpage)

Display detection boxes in the frontend instead of OpenCV:

1. **Start the detection stream server** (pulls from ESP32/webcam, runs detection, serves MJPEG with boxes):
   ```bash
   python detect_stream_server.py
   # Or: python detect_stream_server.py --api   (Roboflow workflows)
   # Or: python detect_stream_server.py --local (local best.pt)
   ```

2. **Set CAMERA_SOURCE** if using ESP32:
   ```bash
   $env:CAMERA_SOURCE = "http://YOUR_ESP32_IP/stream"
   python detect_stream_server.py
   ```

3. **Run the frontend** (defaults to `http://localhost:5000/stream`):
   ```bash
   cd v1_plant_music_player/frontend
   npm install && npm run dev
   ```

   To use raw ESP32 stream (no boxes): `VITE_STREAM_URL=http://172.19.129.149/stream npm run dev`

## Project Structure

- `detect_stream_server.py` – Flask server: detection + MJPEG stream with boxes for web
- `webcam_rose_detect.py` – main detection script (Roboflow API or local best.pt)
- `run_rose_detect.ps1` – run detection (Windows)
- `run_training.ps1` – run training (Windows)
- `train_yolo11_roboflow.py` – YOLO11 training on Roboflow
- `ESP32_CAM_Stream/` – ESP32-CAM streaming sketch
- `ESP32-CAM_CameraWebServer/` – full CameraWebServer for ESP32-CAM
- `esp32cam_get_ip/` – WiFi diagnostic sketch
