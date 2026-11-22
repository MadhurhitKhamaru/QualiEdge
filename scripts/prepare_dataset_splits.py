#!/usr/bin/env python3
"""
scripts/prepare_dataset_splits.py

Splits dataset into stratified Train (80%), Validation (10%), and Test (10%) sets.
Creates the standardized Ultralytics YOLO folder structure:
  data/processed/images/train/
  data/processed/images/val/
  data/processed/images/test/
  data/processed/labels/train/
  data/processed/labels/val/
  data/processed/labels/test/
"""

import os
import shutil
import random
from pathlib import Path
from collections import defaultdict

# Reproducibility seed
SEED = 42
TRAIN_RATIO = 0.80
VAL_RATIO = 0.10
TEST_RATIO = 0.10

RAW_IMG_DIR = Path("data/raw/IMAGES")
LABELS_DIR = Path("data/labels")
PROCESSED_DIR = Path("data/processed")

def prepare_splits():
    random.seed(SEED)

    if not RAW_IMG_DIR.exists():
        raise FileNotFoundError(f"Raw images directory {RAW_IMG_DIR} not found. Run download_neu_dataset.py first.")

    # Find all images (.jpg, .png, .bmp)
    img_files = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp"):
        img_files.extend(list(RAW_IMG_DIR.glob(ext)))

    if not img_files:
        raise FileNotFoundError(f"No image files found in {RAW_IMG_DIR}")

    print(f"[INFO] Discovered {len(img_files)} total images.")

    # Group by defect class prefix (e.g. 'crazing_001.jpg' -> 'crazing')
    class_groups = defaultdict(list)
    for img_path in img_files:
        # e.g., 'scratches_012.jpg' -> class prefix 'scratches'
        class_name = img_path.stem.split("_")[0]
        class_groups[class_name].append(img_path)

    print(f"[INFO] Identified {len(class_groups)} distinct class distributions:")
    for c_name, c_list in class_groups.items():
        print(f"  • {c_name}: {len(c_list)} items")

    # Clean and create destination folders
    splits = ["train", "val", "test"]
    for split in splits:
        (PROCESSED_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (PROCESSED_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    split_counts = defaultdict(lambda: defaultdict(int))

    # Stratified partition per class
    for class_name, items in class_groups.items():
        random.shuffle(items)
        n = len(items)
        n_train = int(n * TRAIN_RATIO)
        n_val = int(n * VAL_RATIO)
        
        train_items = items[:n_train]
        val_items = items[n_train:n_train + n_val]
        test_items = items[n_train + n_val:]

        for split_name, split_list in [("train", train_items), ("val", val_items), ("test", test_items)]:
            for img_path in split_list:
                label_path = LABELS_DIR / f"{img_path.stem}.txt"

                # Destination paths
                dest_img = PROCESSED_DIR / "images" / split_name / img_path.name
                dest_lbl = PROCESSED_DIR / "labels" / split_name / f"{img_path.stem}.txt"

                # Copy image
                shutil.copy2(img_path, dest_img)

                # Copy label if exists, else create empty label file (background / normal)
                if label_path.exists():
                    shutil.copy2(label_path, dest_lbl)
                else:
                    dest_lbl.touch()

                split_counts[split_name][class_name] += 1

    print("\n[SUCCESS] Dataset successfully partitioned:")
    for split in splits:
        total = sum(split_counts[split].values())
        print(f"  • {split.upper()}: {total} images ({dict(split_counts[split])})")

    print(f"\n[INFO] Dataset ready in {PROCESSED_DIR.resolve()}")

if __name__ == "__main__":
    prepare_splits()
