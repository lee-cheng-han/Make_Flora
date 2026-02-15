"""
Detection stream server – runs rose/flower detection and serves MJPEG with boxes for web display.

Usage:
    pip install flask
    python detect_stream_server.py              # default: ESP32 stream + Roboflow API
    python detect_stream_server.py --api        # Roboflow workflows
    python detect_stream_server.py --local      # local best.pt
    python detect_stream_server.py --demo       # demo boxes only

Frontend: set stream URL to http://localhost:5000/stream
Env: CAMERA_SOURCE, ROBOFLOW_API_KEY
"""

import io
import os
import sys
import time
import threading

# Add parent dir for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from webcam_rose_detect import (
    MjpegStreamReader,
    CAMERA_SOURCE,
    ROBOFLOW_PROJECT,
    ROBOFLOW_VERSION,
    ROBOFLOW_WORKFLOWS,
    WORKFLOW_ROSES_ONLY,
    WORKFLOW_FLOWERS_ONLY,
    API_INTERVAL_SEC,
    BOX_SMOOTH_ALPHA,
    EMPTY_FRAMES_TO_CLEAR,
    find_local_model,
    run_local_inference,
    run_roboflow_workflow,
    run_roboflow_hosted,
    parse_api_predictions,
    remove_flower_overlap_with_roses,
    smooth_boxes,
    draw_boxes,
)
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import cv2
import numpy as np

try:
    from flask import Flask, Response
except ImportError:
    print("Install Flask: pip install flask")
    sys.exit(1)

# Server config
HOST = os.getenv("DETECT_HOST", "0.0.0.0")
PORT = int(os.getenv("DETECT_PORT", "5000"))
STREAM_PATH = "/stream"

app = Flask(__name__)

# Shared state for detection loop
_latest_jpeg = {"data": None, "lock": threading.Lock()}
_latest_detection = {"classes": [], "lock": threading.Lock()}

# Floriography content for each detected class (name, language, poetic)
FLORIOGRAPHY = {
    "rose": {
        "name": "Rose",
        "language": "Roses symbolize love, passion, and beauty. The red rose speaks the language of the heart.",
        "poetic": "A rose by any other name would smell as sweet—love speaks in petals, and every thorn guards a bloom.",
    },
    "flower cluster": {
        "name": "Flower Cluster",
        "language": "A gathering of blooms speaks of abundance, joy, and the beauty of nature in full expression.",
        "poetic": "Where flowers bloom, so does hope—a garden is a friend you can visit anytime.",
    },
}


def detection_loop():
    """Background thread: read frames, run detection, draw boxes, encode to JPEG."""
    use_api = "--api" in sys.argv or "--hosted" in sys.argv
    use_local_only = "--local" in sys.argv
    use_demo = "--demo" in sys.argv
    local_weights = find_local_model()
    use_hosted = "--hosted" in sys.argv

    if use_demo:
        mode = "demo"
    elif use_local_only and local_weights:
        mode = "local"
    else:
        mode = "api" if use_api or not local_weights else "local"

    if "--roses" in sys.argv:
        workflows = WORKFLOW_ROSES_ONLY
    elif "--flowers" in sys.argv:
        workflows = WORKFLOW_FLOWERS_ONLY
    else:
        workflows = ROBOFLOW_WORKFLOWS

    try:
        cam_src = int(CAMERA_SOURCE) if CAMERA_SOURCE.isdigit() else CAMERA_SOURCE
    except (ValueError, AttributeError):
        cam_src = CAMERA_SOURCE

    use_url_stream = isinstance(cam_src, str) and cam_src.startswith("http")
    cap = None
    mjpeg_reader = None

    if use_url_stream:
        try:
            import socket
            p = urlparse(cam_src)
            host, port = p.hostname, p.port or 80
            sock = socket.create_connection((host, port), timeout=8)
            sock.close()
        except Exception:
            use_url_stream = False
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                cap = cv2.VideoCapture(cv2.CAP_ANY)
    if not use_url_stream and cap is None:
        cap = cv2.VideoCapture(cam_src)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if use_url_stream:
        mjpeg_reader = MjpegStreamReader(cam_src, timeout=45)

    api_boxes = []
    api_lock = threading.Lock()
    api_prev = {"boxes": []}
    api_busy = {"ok": False}
    api_empty_count = {"n": 0}
    last_api_time = 0

    def send_frame_to_api(frame_copy):
        try:
            h, w = frame_copy.shape[:2]
            all_boxes = []
            if use_hosted:
                resp = run_roboflow_hosted(frame_copy, ROBOFLOW_PROJECT, ROBOFLOW_VERSION)
                raw = parse_api_predictions(resp, h, w, default_class="rose")
                for b in raw:
                    if b[5] >= 0.3:
                        all_boxes.append((*b[:6], (0, 255, 0)))
            else:
                for wf_id, label, color, min_conf in workflows:
                    try:
                        resp = run_roboflow_workflow(frame_copy, wf_id)
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

    def frame_source():
        if use_url_stream:
            try:
                yield from mjpeg_reader
            except Exception:
                fb = cv2.VideoCapture(0)
                if fb.isOpened():
                    fb.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    while True:
                        ret, f = fb.read()
                        if not ret:
                            break
                        yield f
        else:
            while True:
                ret, f = cap.read()
                if not ret:
                    break
                yield f

    for frame in frame_source():
        if mode == "demo":
            h, w = frame.shape[:2]
            box_w, box_h = w * 0.25, h * 0.25
            xc, yc = w / 2, h / 2
            demo_box = (xc, yc, box_w, box_h, "rose (demo)", 0.95, (0, 255, 0))
            draw_boxes(frame, [demo_box])
            cv2.putText(frame, "Demo mode", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            _update_detection([demo_box])
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
            _update_detection(boxes)
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
            _update_detection(boxes)

        _, jpg = cv2.imencode(".jpg", frame)
        with _latest_jpeg["lock"]:
            _latest_jpeg["data"] = jpg.tobytes()


def _update_detection(boxes):
    """Extract unique class names from boxes and store for API."""
    classes = []
    seen = set()
    for b in boxes:
        cls_name = (b[4] if len(b) > 4 else "").lower().strip()
        if cls_name and cls_name not in seen:
            seen.add(cls_name)
            # Map variants to our keys
            if "rose" in cls_name:
                classes.append("rose")
            elif "flower" in cls_name or "cluster" in cls_name:
                classes.append("flower cluster")
            else:
                classes.append(cls_name)
    with _latest_detection["lock"]:
        _latest_detection["classes"] = classes


def generate_stream():
    """Yield MJPEG frames for HTTP response."""
    while True:
        with _latest_jpeg["lock"]:
            data = _latest_jpeg["data"]
        if data:
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + data + b"\r\n")
        time.sleep(0.033)  # ~30 fps


@app.route("/detection")
def detection():
    """Return current detection for Floriography panel (name, language, poetic)."""
    with _latest_detection["lock"]:
        classes = list(_latest_detection["classes"])
    # Prefer rose, then flower cluster
    if "rose" in classes:
        data = FLORIOGRAPHY["rose"]
    elif "flower cluster" in classes:
        data = FLORIOGRAPHY["flower cluster"]
    elif classes:
        data = FLORIOGRAPHY.get(classes[0], {"name": classes[0].title(), "language": "", "poetic": ""})
    else:
        data = {
            "name": "Waiting...",
            "language": "Capture a flower to see its mystery.",
            "poetic": "The silence of nature is waiting to be heard.",
        }
    return Response(
        __import__("json").dumps(data),
        mimetype="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.route(STREAM_PATH)
def stream():
    return Response(
        generate_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache", "Access-Control-Allow-Origin": "*"},
    )


if __name__ == "__main__":
    print(f"Starting detection stream server on http://{HOST}:{PORT}{STREAM_PATH}")
    print("Mode: api (use --local for best.pt, --demo for sample boxes)")
    t = threading.Thread(target=detection_loop, daemon=True)
    t.start()
    time.sleep(2)
    app.run(host=HOST, port=PORT, threaded=True)
