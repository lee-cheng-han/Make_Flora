"""
Train YOLOv11 for tiny white flower detection on Roboflow.

Downloads your flower dataset from Roboflow and trains YOLO11.
Set ROBOFLOW_PROJECT to your Roboflow project name (e.g. tiny-white-flowers).

Usage:
    pip install roboflow ultralytics
    set ROBOFLOW_PROJECT=tiny-white-flowers   # your project name
    python train_flower_detect.py

Quick test (2 epochs):
    python train_flower_detect.py --test
"""

import os
from pathlib import Path

# -----------------------------------------------------------------------------
# Configuration – adjust these or set environment variables
# -----------------------------------------------------------------------------
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "J1p7kkelMCbw8wVR7Zwg")
WORKSPACE = os.getenv("ROBOFLOW_WORKSPACE", "nic-aohns")
# Your Roboflow project with tiny white flower annotations
PROJECT = os.getenv("ROBOFLOW_PROJECT", "tiny-white-flowers")
VERSION = os.getenv("ROBOFLOW_VERSION", "auto")

# Output directory (separate from rose training)
OUTPUT_DIR = Path(os.getenv("TRAIN_OUTPUT_DIR", "./roboflow_flower_detect"))
MODEL_SIZE = os.getenv("YOLO11_MODEL", "n")
EPOCHS = int(os.getenv("TRAIN_EPOCHS", "100"))
# Use 640 or 1280 for tiny objects – higher res helps detect small flowers
IMGSZ = int(os.getenv("TRAIN_IMGSZ", "640"))
BATCH = int(os.getenv("TRAIN_BATCH", "16"))
DEVICE = os.getenv("TRAIN_DEVICE", "")
PATIENCE = int(os.getenv("TRAIN_PATIENCE", "50"))


def main():
    import roboflow
    from ultralytics import YOLO

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Flower detection training – project=%s" % PROJECT)
    print("Output directory: %s" % OUTPUT_DIR.resolve())

    rf = roboflow.Roboflow(api_key=ROBOFLOW_API_KEY)
    project = rf.workspace(WORKSPACE).project(PROJECT)
    versions = project.get_version_information()

    if not versions:
        print("\n" + "=" * 60)
        print("  NO DATASET VERSION FOUND")
        print("=" * 60)
        print("  Create a Roboflow project for tiny white flowers first:")
        print("  1. Go to https://app.roboflow.com/%s" % WORKSPACE)
        print("  2. Create new project 'tiny-white-flowers' (Object Detection)")
        print("  3. Upload images with tiny white flowers")
        print("  4. Annotate flowers with bounding boxes")
        print("  5. Versions -> Create New Version -> Generate")
        print("  6. Run: set ROBOFLOW_PROJECT=tiny-white-flowers")
        print("  7. Run this script again")
        print("=" * 60 + "\n")
        raise SystemExit(1)

    version_num = str(versions[0]["id"]).split("/")[-1] if VERSION == "auto" else str(int(VERSION))
    print("Using Roboflow workspace=%s project=%s version=%s" % (WORKSPACE, PROJECT, version_num))

    print("\nDownloading dataset from Roboflow...")
    dataset = project.version(version_num).download("yolov8")

    dataset_path = Path(dataset.location)
    data_yaml = dataset_path / "data.yaml"
    if not data_yaml.exists():
        for candidate in [dataset_path, dataset_path.parent]:
            c = candidate / "data.yaml"
            if c.exists():
                data_yaml = c
                break
    if not data_yaml.exists():
        raise FileNotFoundError(
            "data.yaml not found after download. Check dataset at app.roboflow.com."
        )

    print("Dataset config: %s" % data_yaml)

    model_name = "yolo11%s.pt" % MODEL_SIZE
    print("\nLoading YOLO11 model: %s" % model_name)
    model = YOLO(model_name)

    print("\n" + "=" * 60)
    print("  TRAINING STARTED (tiny white flowers)  –  epochs=%s  imgsz=%s" % (EPOCHS, IMGSZ))
    print("=" * 60 + "\n")
    results = model.train(
        data=str(data_yaml),
        epochs=EPOCHS,
        imgsz=IMGSZ,
        batch=BATCH,
        patience=PATIENCE,
        project=str(OUTPUT_DIR / "runs" / "detect"),
        name="flower_train",
        exist_ok=True,
        device=DEVICE if DEVICE else None,
    )

    best_weights = Path(model.trainer.best) if hasattr(model.trainer, "best") else None
    print("\n" + "=" * 60)
    print("  TRAINING FINISHED")
    print("=" * 60)
    if best_weights and best_weights.exists():
        print("  Best weights: %s" % best_weights)
    print("=" * 60 + "\n")
    return results


if __name__ == "__main__":
    if "--test" in __import__("sys").argv or "-t" in __import__("sys").argv:
        os.environ.setdefault("TRAIN_EPOCHS", "2")
        print("Quick test mode: 2 epochs\n")
    main()
