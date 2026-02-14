"""
Webcam flower detection – roses + flowers (Roboflow APIs or local YOLO).

Usage:
    pip install opencv-python ultralytics
    python webcam_rose_detect.py              # auto: local model or API
    python webcam_rose_detect.py --demo       # draw sample boxes (verify display works)
    python webcam_rose_detect.py --api        # both workflows (roses + flower cluster)
    python webcam_rose_detect.py --roses     # only find-roses workflow
    python webcam_rose_detect.py --flowers   # only find-cluster-of-flowers workflow
    python webcam_rose_detect.py --hosted     # detect.roboflow.com (needs trained version)
    python webcam_rose_detect.py --local      # local best.pt (run train_yolo11_roboflow.py first)
    python webcam_rose_detect.py --debug      # print API response structure

No boxes? Your Roboflow projects need a trained version. Train: python train_yolo11_roboflow.py
Press 'q' to quit.
"""

import base64
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np


class MjpegStreamReader:
    """Read MJPEG stream from ESP32-CAM (more reliable than cv2.VideoCapture on Windows)."""
    def __init__(self, url, timeout=10):
        self.url = url
        self.timeout = timeout
        self._stream = None

    def __iter__(self):
        req = urllib.request.Request(self.url, headers={"User-Agent": "Mozilla/5.0"})
        self._stream = urllib.request.urlopen(req, timeout=self.timeout)
        ctype = self._stream.headers.get("Content-Type", "")
        boundary_match = re.search(r'boundary=["\']?([^\s;"\']+)', ctype)
        boundary = boundary_match.group(1).strip().encode() if boundary_match else b""

        buf = b""
        while True:
            chunk = self._stream.read(4096)
            if not chunk:
                break
            buf += chunk
            a = buf.find(b"--" + boundary)
            if a < 0:
                continue
            b = buf.find(b"\r\n\r\n", a)
            if b < 0:
                continue
            header = buf[a:b].decode(errors="ignore")
            cl_match = re.search(r"Content-Length:\s*(\d+)", header, re.I)
            if not cl_match:
                buf = buf[b:]
                continue
            size = int(cl_match.group(1))
            start = b + 4
            while len(buf) < start + size:
                more = self._stream.read(4096)
                if not more:
                    break
                buf += more
            if len(buf) >= start + size:
                jpg = buf[start:start + size]
                buf = buf[start + size:]
                arr = np.frombuffer(jpg, dtype=np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame is not None:
                    yield frame

    def release(self):
        if self._stream:
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "J1p7kkelMCbw8wVR7Zwg")
ROBOFLOW_WORKSPACE = "nic-aohns"
# Workflows: https://serverless.roboflow.com/nic-aohns/workflows/<id>
# (workflow_id, display_label, BGR color, min_confidence)
ROBOFLOW_WORKFLOWS = [
    ("find-roses", "rose", (0, 255, 0), 0),              # green – your rose workflow
    ("find-cluster-of-flowers", "flower cluster", (255, 0, 255), 0.4),  # magenta – your flower workflow
]
WORKFLOW_ROSES_ONLY = [("find-roses", "rose", (0, 255, 0), 0)]
WORKFLOW_FLOWERS_ONLY = [("find-cluster-of-flowers", "flower cluster", (255, 0, 255), 0.4)]
# Hosted API: project ID from Roboflow (e.g. find-roses-llg6n)
ROBOFLOW_PROJECT = os.getenv("ROBOFLOW_PROJECT", "find-roses-llg6n")
ROBOFLOW_VERSION = os.getenv("ROBOFLOW_VERSION", "1")
# Where training saves best.pt (override with env ROBOFLOW_WEIGHTS or BEST_WEIGHTS)
TRAIN_RUNS = Path(__file__).resolve().parent / "roboflow_yolo11" / "runs" / "detect" / "train"
BEST_WEIGHTS_DEFAULT = TRAIN_RUNS / "weights" / "best.pt"
BEST_WEIGHTS = Path(os.getenv("BEST_WEIGHTS", os.getenv("ROBOFLOW_WEIGHTS", str(BEST_WEIGHTS_DEFAULT))))
# API mode: how often to send frames (seconds). Lower = faster updates but more API calls.
API_INTERVAL_SEC = 0.08
# Box smoothing: blend new boxes with previous. Higher = snappier (less lag), lower = smoother.
BOX_SMOOTH_ALPHA = 0.98
# Max size for API upload (smaller = faster). Set to 0 to use full frame.
API_IMAGE_SIZE = 416
# Require this many consecutive empty API responses before clearing boxes (reduces flicker).
EMPTY_FRAMES_TO_CLEAR = 2
# Debug: print first API response to diagnose parsing.
DEBUG_API_RESPONSE = "--debug" in sys.argv or os.getenv("DEBUG_API", "").lower() in ("1", "true", "yes")

# Camera source: 0 = built-in webcam, or URL for ESP32-CAM
# CameraWebServer uses port 80: http://IP/stream  (some use :81)
CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "http://172.19.129.149/stream")


def find_local_model():
    if BEST_WEIGHTS.exists():
        return str(BEST_WEIGHTS)
    # Ultralytics sometimes saves best.pt next to train folder
    alt = TRAIN_RUNS.parent / "best.pt"
    if alt.exists():
        return str(alt)
    return None


def run_local_inference(model_path, frame):
    from ultralytics import YOLO
    model = getattr(run_local_inference, "_model", None)
    if model is None:
        run_local_inference._model = YOLO(model_path)
        model = run_local_inference._model
    results = model(frame, verbose=False)
    return results[0]


def run_roboflow_workflow(frame, workflow_id):
    """Call Roboflow workflow API (serverless)."""
    img = frame
    if API_IMAGE_SIZE > 0:
        h, w = frame.shape[:2]
        if max(h, w) > API_IMAGE_SIZE:
            scale = API_IMAGE_SIZE / max(h, w)
            nw, nh = int(w * scale), int(h * scale)
            img = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode(".jpg", img)
    b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
    url = f"https://serverless.roboflow.com/{ROBOFLOW_WORKSPACE}/workflows/{workflow_id}"
    body = json.dumps({
        "api_key": ROBOFLOW_API_KEY,
        "inputs": {"image": {"type": "base64", "value": b64}},
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def run_roboflow_hosted(frame, project_id, version):
    """Call detect.roboflow.com hosted API - returns standard {predictions, image} format."""
    img = frame
    if API_IMAGE_SIZE > 0:
        h, w = frame.shape[:2]
        if max(h, w) > API_IMAGE_SIZE:
            scale = API_IMAGE_SIZE / max(h, w)
            nw, nh = int(w * scale), int(h * scale)
            img = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode(".jpg", img)
    b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
    url = f"https://detect.roboflow.com/{project_id}/{version}?api_key={ROBOFLOW_API_KEY}"
    req = urllib.request.Request(url, data=b64.encode(), headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _parse_one_pred(p, img_w, img_h, frame_w, frame_h, default_class):
    """Parse a single prediction dict into (x_center, y_center, w, h, class, conf)."""
    scale_x = frame_w / img_w if img_w else 1
    scale_y = frame_h / img_h if img_h else 1
    cls = p.get("class") or p.get("class_name") or default_class
    conf = float(p.get("confidence") or p.get("class_confidence") or 0)

    # xyxy format: [x1, y1, x2, y2]
    xyxy = p.get("xyxy")
    if xyxy and isinstance(xyxy, (list, tuple)) and len(xyxy) >= 4:
        x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])
        xc = (x1 + x2) / 2
        yc = (y1 + y2) / 2
        bw = x2 - x1
        bh = y2 - y1
        return (xc * scale_x, yc * scale_y, bw * scale_x, bh * scale_y, cls, conf)

    x = float(p.get("x", 0))
    y = float(p.get("y", 0))
    bw = float(p.get("width") or p.get("w", 0))
    bh = float(p.get("height") or p.get("h", 0))

    # Roboflow may return normalized (0-1) coords
    if 0 < x <= 1 and 0 < y <= 1:
        x, y = x * img_w, y * img_h
    if 0 < bw <= 1:
        bw *= img_w
    if 0 < bh <= 1:
        bh *= img_h

    # Assume center format (standard); if top-left, add half width/height
    if bw > 0 and bh > 0:
        x_center = x * scale_x
        y_center = y * scale_y
        box_w = bw * scale_x
        box_h = bh * scale_y
    else:
        x_center = x * scale_x
        y_center = y * scale_y
        box_w = 20 * scale_x  # fallback
        box_h = 20 * scale_y
    return (x_center, y_center, box_w, box_h, cls, conf)


def _parse_sv_detections(block, iw, ih, frame_w, frame_h, default_class):
    """Parse sv.Detections format: xyxy, confidence, class_id, data.class_name as arrays."""
    out = []
    xyxy = block.get("xyxy")
    if not isinstance(xyxy, (list, tuple)) or len(xyxy) == 0:
        return out
    confs = block.get("confidence") or block.get("confidences") or []
    if not isinstance(confs, (list, tuple)):
        confs = []
    data = block.get("data") or {}
    class_names = data.get("class_name") if isinstance(data.get("class_name"), (list, tuple)) else []
    scale_x = frame_w / iw if iw else 1
    scale_y = frame_h / ih if ih else 1
    for i, box in enumerate(xyxy):
        if not isinstance(box, (list, tuple)) or len(box) < 4:
            continue
        x1, y1, x2, y2 = float(box[0]), float(box[1]), float(box[2]), float(box[3])
        xc = ((x1 + x2) / 2) * scale_x
        yc = ((y1 + y2) / 2) * scale_y
        bw = (x2 - x1) * scale_x
        bh = (y2 - y1) * scale_y
        conf = float(confs[i]) if i < len(confs) else 0.5
        cls = class_names[i] if i < len(class_names) else default_class
        out.append((xc, yc, bw, bh, str(cls), conf))
    return out


def parse_api_predictions(api_response, frame_h, frame_w, default_class="object"):
    """Convert Roboflow workflow/inference response to list of (x_center, y_center, w, h, class, conf)."""
    out = []
    img_w, img_h = frame_w, frame_h

    def add_preds(preds, iw, ih):
        nonlocal out
        if not isinstance(preds, list):
            return
        for p in preds:
            if isinstance(p, dict):
                out.append(_parse_one_pred(p, iw, ih, frame_w, frame_h, default_class))

    try:
        # Legacy/direct format: {"predictions": [...], "image": {width, height}}
        preds = api_response.get("predictions")
        img = api_response.get("image") or {}
        if isinstance(img, list):
            img = img[0] if img else {}
        iw = img.get("width") or frame_w
        ih = img.get("height") or frame_h
        if isinstance(preds, list):
            add_preds(preds, iw, ih)
            return out

        # Workflow outputs format
        for block in api_response.get("outputs", []):
            pred_block = block.get("predictions") if isinstance(block, dict) else None
            if pred_block is None:
                pred_block = block
            img_info = pred_block.get("image", {}) if isinstance(pred_block, dict) else {}
            iw = img_info.get("width") or frame_w
            ih = img_info.get("height") or frame_h

            # sv.Detections format: xyxy, confidence, data.class_name as arrays
            if isinstance(pred_block, dict) and "xyxy" in pred_block:
                out.extend(_parse_sv_detections(pred_block, iw, ih, frame_w, frame_h, default_class))
                continue

            preds = pred_block.get("predictions", []) if isinstance(pred_block, dict) else []
            add_preds(preds, iw, ih)
    except Exception:
        pass
    return out


def _box_iou(box_a, box_b):
    """IoU of two boxes (xc, yc, w, h). Returns 0-1."""
    xa, ya, wa, ha = box_a[0], box_a[1], box_a[2], box_a[3]
    xb, yb, wb, hb = box_b[0], box_b[1], box_b[2], box_b[3]
    ax1, ay1 = xa - wa / 2, ya - ha / 2
    ax2, ay2 = xa + wa / 2, ya + ha / 2
    bx1, by1 = xb - wb / 2, yb - hb / 2
    bx2, by2 = xb + wb / 2, yb + hb / 2
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_a = wa * ha
    area_b = wb * hb
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0


def remove_flower_overlap_with_roses(all_boxes):
    """Keep roses; drop flower boxes that overlap roses (rose = rose only, flower = non-rose only)."""
    roses = [b for b in all_boxes if len(b) > 6 and b[6] == (0, 255, 0)]
    flowers = [b for b in all_boxes if len(b) > 6 and b[6] == (255, 0, 255)]
    kept_flowers = []
    for fb in flowers:
        if any(_box_iou(fb, rb) > 0.3 for rb in roses):
            continue
        kept_flowers.append(fb)
    return roses + kept_flowers


def smooth_boxes(prev_boxes, new_boxes, alpha):
    """Blend new boxes with previous for smoother transitions. Box = (xc, yc, w, h, cls, conf) or +color."""
    if not prev_boxes or alpha <= 0:
        return new_boxes
    if not new_boxes:
        return []  # No detections -> clear boxes
    out = []
    for i, nb in enumerate(new_boxes):
        xc, yc, w, h, cls, conf = nb[:6]
        color = nb[6] if len(nb) > 6 else (0, 255, 0)
        if i < len(prev_boxes):
            pb = prev_boxes[i]
            pxc, pyc, pw, ph = pb[0], pb[1], pb[2], pb[3]
            xc = alpha * xc + (1 - alpha) * pxc
            yc = alpha * yc + (1 - alpha) * pyc
            w = alpha * w + (1 - alpha) * pw
            h = alpha * h + (1 - alpha) * ph
        out.append((xc, yc, w, h, cls, conf, color))
    return out


def draw_boxes(frame, boxes, default_color=(0, 255, 0), thickness=2):
    for box in boxes:
        xc, yc, w, h, cls, conf = box[:6]
        color = box[6] if len(box) > 6 else default_color
        x1 = int(xc - w / 2)
        y1 = int(yc - h / 2)
        x2 = int(xc + w / 2)
        y2 = int(yc + h / 2)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
        label = f"{cls} {conf:.2f}"
        cv2.putText(frame, label, (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)


def main():
    use_api = "--api" in sys.argv or "--hosted" in sys.argv
    use_local_only = "--local" in sys.argv
    use_demo = "--demo" in sys.argv
    local_weights = find_local_model()

    if use_local_only and not local_weights:
        print("No local model found. Either:")
        print("  1. Train: python train_yolo11_roboflow.py  (or .\\run_training.ps1)")
        print("  2. Or set path: $env:BEST_WEIGHTS = \"C:\\path\\to\\best.pt\"")
        print("Expected path:", BEST_WEIGHTS)
        sys.exit(1)
    if use_demo:
        mode = "demo"
        print("Demo mode – showing sample boxes. Train a model for real detection.")
    elif use_api:
        mode = "hosted" if "--hosted" in sys.argv else "api"
    elif local_weights:
        mode = "local"
        print("Using local model:", local_weights)
    else:
        mode = "hosted" if "--hosted" in sys.argv else "api"
        if mode == "hosted":
            print(f"Using Roboflow hosted API: {ROBOFLOW_PROJECT}/{ROBOFLOW_VERSION}")
        else:
            print("No local model found. Using Roboflow workflow API. Try --hosted if boxes don't show.")

    # Camera: 0 = built-in, or URL for ESP32-CAM stream
    try:
        cam_src = int(CAMERA_SOURCE) if CAMERA_SOURCE.isdigit() else CAMERA_SOURCE
    except (ValueError, AttributeError):
        cam_src = CAMERA_SOURCE

    use_url_stream = isinstance(cam_src, str) and cam_src.startswith("http")
    cap = None
    mjpeg_reader = None
    if use_url_stream:
        print("Connecting to ESP32-CAM stream:", cam_src)
        try:
            p = urlparse(cam_src)
            host, port = p.hostname, p.port or 80
            sock = socket.create_connection((host, port), timeout=8)
            sock.close()
        except (TimeoutError, OSError, socket.timeout) as e:
            print("ESP32-CAM stream connection failed:", e)
            print("Using built-in webcam instead. For ESP32: check same WiFi and IP (Serial Monitor).")
            use_url_stream = False
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("Could not open webcam.")
                sys.exit(1)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        else:
            mjpeg_reader = MjpegStreamReader(cam_src, timeout=45)
    if not use_url_stream and cap is None:
        cap = cv2.VideoCapture(cam_src)
        if not cap.isOpened():
            print("Could not open camera.")
            sys.exit(1)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    # API mode: run inference in background so video never blocks
    api_boxes = []
    api_lock = threading.Lock()
    api_prev = {"boxes": []}
    api_busy = {"ok": False}
    api_empty_count = {"n": 0}

    _debug_done = {"ok": False}
    use_hosted = "--hosted" in sys.argv
    if "--roses" in sys.argv:
        workflows = WORKFLOW_ROSES_ONLY
    elif "--flowers" in sys.argv:
        workflows = WORKFLOW_FLOWERS_ONLY
    else:
        workflows = ROBOFLOW_WORKFLOWS

    def send_frame_to_api(frame_copy):
        try:
            h, w = frame_copy.shape[:2]
            all_boxes = []
            if use_hosted:
                # Use detect.roboflow.com - standard format, single model
                resp = run_roboflow_hosted(frame_copy, ROBOFLOW_PROJECT, ROBOFLOW_VERSION)
                raw = parse_api_predictions(resp, h, w, default_class="rose")
                for b in raw:
                    if b[5] >= 0.3:
                        all_boxes.append((*b[:6], (0, 255, 0)))
            else:
                # Call workflow API(s) – find-cluster-of-flowers and/or find-roses
                with ThreadPoolExecutor(max_workers=2) as ex:
                    futures = {
                        ex.submit(run_roboflow_workflow, frame_copy, wf_id): (wf_id, label, color, min_conf)
                        for wf_id, label, color, min_conf in workflows
                    }
                for fut in as_completed(futures):
                    wf_id, label, color, min_conf = futures[fut]
                    try:
                        resp = fut.result()
                        if DEBUG_API_RESPONSE and not _debug_done["ok"]:
                            _debug_done["ok"] = True
                            print("[DEBUG] Roboflow response keys:", list(resp.keys()) if isinstance(resp, dict) else type(resp))
                            if isinstance(resp, dict):
                                outs = resp.get("outputs", [])
                                print("[DEBUG] outputs len:", len(outs))
                                for i, o in enumerate(outs[:2]):
                                    print(f"[DEBUG] outputs[{i}] keys:", list(o.keys()) if isinstance(o, dict) else type(o))
                                    pb = o.get("predictions", o) if isinstance(o, dict) else o
                                    if isinstance(pb, dict):
                                        preds = pb.get("predictions", [])
                                        print(f"[DEBUG]   predictions count: {len(preds) if isinstance(preds, list) else 'N/A'}")
                                        if preds and isinstance(preds, list) and len(preds) > 0:
                                            print("[DEBUG]   first pred keys:", list(preds[0].keys()) if isinstance(preds[0], dict) else preds[0])
                        raw = parse_api_predictions(resp, h, w, default_class=label)
                        for b in raw:
                            if b[5] >= min_conf:
                                all_boxes.append((*b[:6], color))
                    except Exception:
                        pass
            all_boxes = remove_flower_overlap_with_roses(all_boxes)
            if all_boxes:
                api_empty_count["n"] = 0
                smooth = smooth_boxes(api_prev["boxes"], all_boxes, BOX_SMOOTH_ALPHA)
                api_prev["boxes"] = smooth
                with api_lock:
                    api_boxes[:] = smooth
            else:
                api_empty_count["n"] += 1
                if api_empty_count["n"] >= EMPTY_FRAMES_TO_CLEAR:
                    api_prev["boxes"] = []
                    with api_lock:
                        api_boxes[:] = []
        except Exception:
            with api_lock:
                api_boxes[:] = []
        api_busy["ok"] = False

    last_api_time = 0

    print("Stream open. Point at roses or flowers. Press 'q' to quit.")
    print("Mode:", mode)

    def frame_source():
        if use_url_stream:
            try:
                yield from mjpeg_reader
            except (TimeoutError, OSError, ConnectionResetError, BrokenPipeError, urllib.error.URLError, socket.timeout) as e:
                print("ESP32-CAM stream failed:", e)
                print("Using built-in webcam instead.")
                cap_fb = cv2.VideoCapture(0)
                if cap_fb.isOpened():
                    cap_fb.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    while True:
                        ret, frame = cap_fb.read()
                        if not ret:
                            break
                        yield frame
                return
        else:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                yield frame

    for frame in frame_source():
        if mode == "demo":
            h, w = frame.shape[:2]
            box_w, box_h = w * 0.25, h * 0.25
            xc, yc = w / 2, h / 2
            demo_box = (xc, yc, box_w, box_h, "rose (demo)", 0.95, (0, 255, 0))
            draw_boxes(frame, [demo_box])
            cv2.putText(frame, "Demo mode – train model for real detection", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        elif mode == "local":
            result = run_local_inference(local_weights, frame)
            boxes = []
            if result.boxes is not None:
                for b in result.boxes:
                    xywh = b.xywh[0].cpu().numpy()
                    cls_id = int(b.cls[0].item())
                    conf = float(b.conf[0].item())
                    cls_name = result.names.get(cls_id, "rose")
                    boxes.append((xywh[0], xywh[1], xywh[2], xywh[3], cls_name, conf))
            draw_boxes(frame, boxes)
        else:
            t = time.time()
            if t - last_api_time >= API_INTERVAL_SEC and not api_busy["ok"]:
                api_busy["ok"] = True
                last_api_time = t
                threading.Thread(target=send_frame_to_api, args=(frame.copy(),), daemon=True).start()
            with api_lock:
                boxes = list(api_boxes)
            draw_boxes(frame, boxes)
            cv2.putText(frame, "Roses & flowers", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        cv2.imshow("Roses & flowers", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    if cap:
        cap.release()
    if mjpeg_reader:
        mjpeg_reader.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
