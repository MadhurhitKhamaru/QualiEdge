#!/usr/bin/env python3
"""
scripts/convert_voc_to_yolo.py

Converts Pascal VOC XML annotations to normalized YOLO format (class_id x_center y_center width height).
Performs strict validation:
1. Normalizes coordinates to [0.0, 1.0] relative to image dimensions.
2. Clamps coordinates to valid image bounding boxes.
3. Checks for degenerate/zero-area bounding boxes.
4. Handles empty annotations for 'normal' defect-free surfaces.
"""

import os
import sys
import glob
import xml.etree.ElementTree as ET
from pathlib import Path

# Map class names to 0-indexed integer IDs
CLASS_MAPPING = {
    "crazing": 0,
    "inclusion": 1,
    "patches": 2,
    "pitted_surface": 3,
    "pitted surface": 3,
    "pitted-surface": 3,
    "rolled_in_scale": 4,
    "rolled-in scale": 4,
    "rolled in scale": 4,
    "rolled-in_scale": 4,
    "scratches": 5,
    "scratch": 5,
    "normal": 6,
    "defect-free": 6
}

def voc_to_yolo_bbox(size_w: float, size_h: float, xmin: float, ymin: float, xmax: float, ymax: float):
    """
    Convert absolute [xmin, ymin, xmax, ymax] to normalized [x_center, y_center, width, height].
    """
    if size_w <= 0 or size_h <= 0:
        raise ValueError(f"Invalid image dimensions: {size_w}x{size_h}")

    # Clip coordinates to image boundary
    xmin = max(0.0, min(float(xmin), size_w))
    ymin = max(0.0, min(float(ymin), size_h))
    xmax = max(0.0, min(float(xmax), size_w))
    ymax = max(0.0, min(float(ymax), size_h))

    box_w = xmax - xmin
    box_h = ymax - ymin

    if box_w <= 0 or box_h <= 0:
        return None  # Discard degenerate zero-area box

    x_center = (xmin + (box_w / 2.0)) / size_w
    y_center = (ymin + (box_h / 2.0)) / size_h
    norm_w = box_w / size_w
    norm_h = box_h / size_h

    # Ensure strictly within [0.0, 1.0]
    return (
        round(min(1.0, max(0.0, x_center)), 6),
        round(min(1.0, max(0.0, y_center)), 6),
        round(min(1.0, max(0.0, norm_w)), 6),
        round(min(1.0, max(0.0, norm_h)), 6)
    )

def convert_annotation_file(xml_path: Path, output_txt_path: Path):
    """Parse single VOC XML and write corresponding YOLO txt file."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    size_elem = root.find("size")
    if size_elem is None:
        raise ValueError(f"No <size> tag found in {xml_path}")

    img_w = float(size_elem.find("width").text)
    img_h = float(size_elem.find("height").text)

    yolo_lines = []

    for obj in root.findall("object"):
        raw_name = obj.find("name").text.strip().lower()
        if raw_name not in CLASS_MAPPING:
            print(f"[WARN] Unknown defect class '{raw_name}' in {xml_path.name}. Skipping.")
            continue

        class_id = CLASS_MAPPING[raw_name]
        # 'normal' class has class_id 6, typically has no bounding boxes (empty file),
        # but if an object tag is present for normal, we can omit bounding box
        if class_id == 6:
            continue

        bndbox = obj.find("bndbox")
        if bndbox is None:
            continue

        xmin = float(bndbox.find("xmin").text)
        ymin = float(bndbox.find("ymin").text)
        xmax = float(bndbox.find("xmax").text)
        ymax = float(bndbox.find("ymax").text)

        bbox = voc_to_yolo_bbox(img_w, img_h, xmin, ymin, xmax, ymax)
        if bbox is not None:
            xc, yc, w, h = bbox
            yolo_lines.append(f"{class_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")

    # Write YOLO label file (even if empty, which signifies background/normal for YOLO)
    output_txt_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(yolo_lines) + ("\n" if yolo_lines else ""))

    return len(yolo_lines)

def convert_all_annotations(xml_dir: Path, output_dir: Path):
    """Batch convert all XMLs in a folder."""
    xml_files = list(xml_dir.glob("*.xml"))
    print(f"[INFO] Found {len(xml_files)} XML annotation files in {xml_dir}")

    total_converted = 0
    total_boxes = 0

    for xml_file in xml_files:
        txt_filename = xml_file.stem + ".txt"
        out_txt = output_dir / txt_filename
        box_count = convert_annotation_file(xml_file, out_txt)
        total_converted += 1
        total_boxes += box_count

    print(f"[SUCCESS] Converted {total_converted} files ({total_boxes} total bounding boxes) into {output_dir}")

if __name__ == "__main__":
    raw_annotations = Path("data/raw/ANNOTATIONS")
    processed_labels = Path("data/labels")

    if not raw_annotations.exists():
        print(f"[ERROR] Directory {raw_annotations} does not exist. Run scripts/download_neu_dataset.py first.")
        sys.exit(1)

    convert_all_annotations(raw_annotations, processed_labels)
