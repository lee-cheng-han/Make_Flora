"""
Train YOLOv11 on a Roboflow dataset.

This script downloads your dataset from Roboflow and trains an Ultralytics YOLO11
object detection model. Configure workspace, project, and version below or via
environment variables.

Usage:
    pip install roboflow ultralytics
    set ROBOFLOW_API_KEY=your_api_key   # Windows
    export ROBOFLOW_API_KEY=your_api_key  # Linux/Mac
    python train_yolo11_roboflow.py

Quick test (2 epochs, to verify setup):
    set TRAIN_EPOCHS=2
    python train_yolo11_roboflow.py
"""

import os
from pathlib import Path

# -----------------------------------------------------------------------------
# Configuration – adjust these or set environment variables
# -----------------------------------------------------------------------------
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "J1p7kkelMCbw8wVR7Zwg")
WORKSPACE = os.getenv("ROBOFLOW_WORKSPACE", "nic-aohns")
PROJECT = os.getenv("ROBOFLOW_PROJECT", "find-roses")
# Use "auto" for latest version, or a number like 1, 2, 3
VERSION = os.getenv("ROBOFLOW_VERSION", "auto")

# Output directory for downloaded dataset and training runs
OUTPUT_DIR = Path(os.getenv("TRAIN_OUTPUT_DIR", "./roboflow_yolo11"))
# YOLO11 model size: n=nano, s=small, m=medium, l=large, x=extra large
MODEL_SIZE = os.getenv("YOLO11_MODEL", "n")
# Training hyperparameters
EPOCHS = int(os.getenv("TRAIN_EPOCHS", "100"))
IMGSZ = int(os.getenv("TRAIN_IMGSZ", "640"))
BATCH = int(os.getenv("TRAIN_BATCH", "16"))
DEVICE = os.getenv("TRAIN_DEVICE", "")  # e.g. "0" for GPU, "" for auto
PATIENCE = int(os.getenv("TRAIN_PATIENCE", "50"))


def main():
    import roboflow
    from ultralytics import YOLO

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Output directory: %s" % OUTPUT_DIR.resolve())

    # --- Get project and check for dataset versions ---
    rf = roboflow.Roboflow(api_key=ROBOFLOW_API_KEY)
    project = rf.workspace(WORKSPACE).project(PROJECT)
    versions = project.get_version_information()

    if not versions:
        print("\n" + "=" * 60)
        print("  NO DATASET VERSION FOUND")
        print("=" * 60)
        print("  Your Roboflow project '%s' has no dataset version yet." % PROJECT)
        print("  You must create one before training:")
        print("  1. Go to https://app.roboflow.com/%s/%s" % (WORKSPACE, PROJECT))
        print("  2. Click 'Versions' in the sidebar")
        print("  3. Click 'Create New Version'")
        print("  4. (Optional) add preprocessing/augmentation, then Generate")
        print("  5. Run this script again")
        print("=" * 60 + "\n")
        raise SystemExit(1)

    version_num = versions[0]["id"] if VERSION == "auto" else int(VERSION)
    print("Using Roboflow workspace=%s project=%s version=%s" % (WORKSPACE, PROJECT, version_num))

    # --- Download dataset from Roboflow (YOLO format, same for YOLOv8/YOLO11) ---
    print("\nDownloading dataset from Roboflow...")
    dataset = project.version(version_num).download("yolov8")

    # Path to dataset config – Roboflow places data.yaml in the version folder
    dataset_path = Path(dataset.location)
    data_yaml = dataset_path / "data.yaml"
    if not data_yaml.exists():
        # Sometimes the SDK returns the parent; look for data.yaml
        for candidate in [dataset_path, dataset_path.parent]:
            c = candidate / "data.yaml"
            if c.exists():
                data_yaml = c
                break
    if not data_yaml.exists():
        raise FileNotFoundError(
            "data.yaml not found after download. Looked in %s. Check dataset at app.roboflow.com."
            % dataset_path
        )

    print("Dataset config: %s" % data_yaml)

    # --- Train YOLO11 ---
    model_name = "yolo11%s.pt" % MODEL_SIZE
    print("\nLoading YOLO11 model: %s" % model_name)
    model = YOLO(model_name)

    print("\n" + "=" * 60)
    print("  TRAINING STARTED  –  epochs=%s  imgsz=%s  batch=%s" % (EPOCHS, IMGSZ, BATCH))
    print("  Watch this terminal for progress. Each epoch will print below.")
    print("=" * 60 + "\n")
    results = model.train(
        data=str(data_yaml),
        epochs=EPOCHS,
        imgsz=IMGSZ,
        batch=BATCH,
        patience=PATIENCE,
        project=str(OUTPUT_DIR / "runs" / "detect"),
        name="train",
        exist_ok=True,
        device=DEVICE if DEVICE else None,
    )

    best_weights = Path(model.trainer.best) if hasattr(model.trainer, "best") else None
    print("\n" + "=" * 60)
    print("  TRAINING FINISHED")
    print("=" * 60)
    if best_weights and best_weights.exists():
        print("  Best weights: %s" % best_weights)
        print("  Test with webcam:  python webcam_rose_detect.py")
    else:
        print("  (No best.pt path; check runs/detect/train/weights/ )")
    print("=" * 60 + "\n")
    return results


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv or "-t" in sys.argv:
        os.environ.setdefault("TRAIN_EPOCHS", "2")
        print("Quick test mode: 2 epochs (use without --test for full training)\n")
    main()
