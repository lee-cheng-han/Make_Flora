"""
Webcam flower detection – roses + flowers (both Roboflow APIs).

Uses your trained YOLO11 model if available; otherwise uses Roboflow
find-roses + find-cluster-of-flowers APIs for detection.

Usage:
    pip install opencv-python ultralytics
    python webcam_rose_detect.py              # auto: local model or both APIs
    python webcam_rose_detect.py --local      # only local model (faster)
    python webcam_rose_detect.py --api        # both Roboflow APIs (find-roses + find-cluster-of-flowers)

Press 'q' to quit.
"""

import base64
import json
import os
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "J1p7kkelMCbw8wVR7Zwg")
ROBOFLOW_WORKSPACE = "nic-aohns"
# Both APIs: (workflow_id, display_label, BGR color)
ROBOFLOW_WORKFLOWS = [
    ("find-roses", "rose", (0, 255, 0)),              # green
    ("find-cluster-of-flowers", "flower cluster", (255, 0, 255)),  # magenta
]
# Where training saves best.pt
TRAIN_RUNS = Path(__file__).resolve().parent / "roboflow_yolo11" / "runs" / "detect" / "train"
BEST_WEIGHTS = TRAIN_RUNS / "weights" / "best.pt"
# API mode: how often to send frames (seconds). Lower = faster updates but more API calls.
API_INTERVAL_SEC = 0.08
# Box smoothing: blend new boxes with previous. Higher = snappier (less lag), lower = smoother.
BOX_SMOOTH_ALPHA = 0.98
# Max size for API upload (smaller = faster). Set to 0 to use full frame.
API_IMAGE_SIZE = 416
# Require this many consecutive empty API responses before clearing boxes (reduces flicker).
EMPTY_FRAMES_TO_CLEAR = 2


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


def run_roboflow_api(frame, workflow_id):
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
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def parse_api_predictions(api_response, frame_h, frame_w, default_class="object"):
    """Convert Roboflow workflow response to list of (x_center, y_center, w, h, class, conf)."""
    out = []
    try:
        for block in api_response.get("outputs", []):
            pred_block = block.get("predictions") or {}
            img_info = pred_block.get("image", {}) if isinstance(pred_block, dict) else {}
            preds = pred_block.get("predictions", []) if isinstance(pred_block, dict) else []
            if not isinstance(preds, list):
                continue
            w = img_info.get("width") or frame_w
            h = img_info.get("height") or frame_h
            scale_x = frame_w / w if w else 1
            scale_y = frame_h / h if h else 1
            for p in preds:
                x = p.get("x", 0)
                y = p.get("y", 0)
                bw = p.get("width", 0)
                bh = p.get("height", 0)
                # Roboflow can return center or top-left; typical is center
                x_center = x * scale_x
                y_center = y * scale_y
                box_w = bw * scale_x
                box_h = bh * scale_y
                cls = p.get("class", default_class)
                conf = float(p.get("confidence", 0))
                out.append((x_center, y_center, box_w, box_h, cls, conf))
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
    use_api = "--api" in sys.argv
    use_local_only = "--local" in sys.argv
    local_weights = find_local_model()

    if use_local_only and not local_weights:
        print("No local model found. Train first: python train_yolo11_roboflow.py")
        print("Expected:", BEST_WEIGHTS)
        sys.exit(1)
    if use_api:
        mode = "api"
    elif local_weights:
        mode = "local"
        print("Using local model:", local_weights)
    else:
        mode = "api"
        print("No local model found. Using Roboflow API (slower). Train for faster webcam: train_yolo11_roboflow.py")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam.")
        sys.exit(1)

    # Reduce buffer for lower latency (smoother video)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    # API mode: run inference in background so video never blocks
    api_boxes = []
    api_lock = threading.Lock()
    api_prev = {"boxes": []}
    api_busy = {"ok": False}
    api_empty_count = {"n": 0}

    def send_frame_to_api(frame_copy):
        try:
            h, w = frame_copy.shape[:2]
            all_boxes = []
            # Call both APIs in parallel
            with ThreadPoolExecutor(max_workers=2) as ex:
                futures = {
                    ex.submit(run_roboflow_api, frame_copy, wf_id): (wf_id, label, color)
                    for wf_id, label, color in ROBOFLOW_WORKFLOWS
                }
                for fut in as_completed(futures):
                    wf_id, label, color = futures[fut]
                    try:
                        resp = fut.result()
                        raw = parse_api_predictions(resp, h, w, default_class=label)
                        for b in raw:
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

    print("Webcam open. Point at roses or flowers. Press 'q' to quit.")
    print("Mode:", mode)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if mode == "local":
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
            cv2.putText(frame, "Roboflow API (roses + flower clusters)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        cv2.imshow("Flower detection", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
