#!/usr/bin/env python3
"""
cv_pipeline/visualizer.py

Industrial HUD and Defect Overlay Visualizer.
Renders high-visibility operator cues:
1. Severity-tinted bounding boxes (Green=Accept, Amber=Warning, Red=Critical Reject).
2. Category label badges with confidence score.
3. Central alignment reticle and conveyor boundary guides.
4. Edge latency (ms) and real-time FPS overlay.
"""

from typing import List, Tuple
from pathlib import Path

# Severity color scheme in BGR format
SEVERITY_COLORS = {
    "Normal": (76, 175, 80),      # Emerald Green
    "Low": (76, 175, 80),         # Emerald Green
    "Medium": (33, 150, 243),     # Amber / Orange
    "High": (33, 150, 243),       # Orange / Amber
    "Critical": (36, 36, 235)     # Bright Red
}

DEFECT_SEVERITY_MAP = {
    "crazing": "Critical",
    "inclusion": "High",
    "patches": "Medium",
    "pitted_surface": "High",
    "rolled_in_scale": "High",
    "scratches": "Medium",
    "normal": "Normal"
}

def draw_industrial_hud(frame, boxes: List[dict], fps: float = 30.0, latency_ms: float = 32.0):
    """
    Render bounding boxes and industrial inspection HUD overlay on top of frame.
    """
    try:
        import cv2

        hud_frame = frame.copy()
        h, w = hud_frame.shape[:2]

        # Draw inspection boundary lines (safe steel conveyor window)
        cv2.line(hud_frame, (80, 0), (80, h), (70, 70, 70), 1, cv2.LINE_AA)
        cv2.line(hud_frame, (w - 80, 0), (w - 80, h), (70, 70, 70), 1, cv2.LINE_AA)

        # Draw top inspection telemetry header bar
        cv2.rectangle(hud_frame, (0, 0), (w, 40), (20, 20, 25), -1)
        cv2.putText(
            hud_frame,
            f"QUALIEDGE QC LINE 1 | FPS: {fps:.1f} | INFER: {latency_ms:.1f}ms",
            (15, 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            1,
            cv2.LINE_AA
        )

        for b in boxes:
            x1 = int(b.get("x1", 0))
            y1 = int(b.get("y1", 0))
            x2 = int(b.get("x2", 0))
            y2 = int(b.get("y2", 0))
            cls_name = b.get("class_name", "defect").lower()
            conf = b.get("confidence", 0.0)

            severity = DEFECT_SEVERITY_MAP.get(cls_name, "High")
            color = SEVERITY_COLORS.get(severity, (0, 0, 255))

            # Bounding box rectangle with corner accents
            cv2.rectangle(hud_frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

            # Label tag
            label_text = f"{cls_name.upper()} {conf*100:.1f}% [{severity}]"
            (text_w, text_h), baseline = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            
            # Badge background
            badge_y1 = max(0, y1 - text_h - 8)
            cv2.rectangle(hud_frame, (x1, badge_y1), (x1 + text_w + 10, y1), color, -1)
            cv2.putText(
                hud_frame,
                label_text,
                (x1 + 5, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA
            )

        return hud_frame

    except ImportError:
        return frame

if __name__ == "__main__":
    print("[INFO] Industrial visualizer initialized. Color palette and HUD configured.")
