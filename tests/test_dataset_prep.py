#!/usr/bin/env python3
"""
tests/test_dataset_prep.py

Automated test suite verifying Phase 2 data preparation modules:
1. Coordinate normalization and clamping for YOLO format.
2. Degenerate bounding box filtering.
3. Augmentation coordinate transformations.
4. Class mapping consistency.
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.convert_voc_to_yolo import voc_to_yolo_bbox, CLASS_MAPPING
from scripts.data_augmentation import rotate_yolo_bbox_90, flip_yolo_bbox_horizontal

class TestDatasetPreparation(unittest.TestCase):

    def test_voc_to_yolo_normalization(self):
        """Test conversion of standard bounding box to normalized YOLO format."""
        # 200x200 image, box from (50, 50) to (150, 150) -> center (100, 100), w=100, h=100
        result = voc_to_yolo_bbox(200, 200, 50, 50, 150, 150)
        self.assertIsNotNone(result)
        xc, yc, w, h = result
        self.assertAlmostEqual(xc, 0.5, places=4)
        self.assertAlmostEqual(yc, 0.5, places=4)
        self.assertAlmostEqual(w, 0.5, places=4)
        self.assertAlmostEqual(h, 0.5, places=4)

    def test_boundary_clamping(self):
        """Test coordinates exceeding image boundaries are clamped safely."""
        # Box starting below 0 and ending beyond 200
        result = voc_to_yolo_bbox(200, 200, -10, -5, 250, 210)
        self.assertIsNotNone(result)
        xc, yc, w, h = result
        self.assertAlmostEqual(xc, 0.5, places=4)
        self.assertAlmostEqual(yc, 0.5, places=4)
        self.assertAlmostEqual(w, 1.0, places=4)
        self.assertAlmostEqual(h, 1.0, places=4)

    def test_zero_area_box_rejection(self):
        """Test degenerate box with zero width or height is safely rejected."""
        result = voc_to_yolo_bbox(200, 200, 50, 50, 50, 100)
        self.assertIsNone(result)

    def test_rotation_transformation(self):
        """Test 90 degree clockwise rotation preserves valid box domain."""
        xc, yc, w, h = 0.3, 0.4, 0.2, 0.1
        n_xc, n_yc, n_w, n_h = rotate_yolo_bbox_90(xc, yc, w, h)
        self.assertAlmostEqual(n_xc, 0.6, places=4)
        self.assertAlmostEqual(n_yc, 0.3, places=4)
        self.assertAlmostEqual(n_w, 0.1, places=4)
        self.assertAlmostEqual(n_h, 0.2, places=4)

    def test_horizontal_flip(self):
        """Test horizontal flip reflects center coordinate across x-axis."""
        xc, yc, w, h = 0.25, 0.5, 0.2, 0.3
        n_xc, n_yc, n_w, n_h = flip_yolo_bbox_horizontal(xc, yc, w, h)
        self.assertAlmostEqual(n_xc, 0.75, places=4)
        self.assertAlmostEqual(n_yc, 0.5, places=4)
        self.assertAlmostEqual(n_w, 0.2, places=4)
        self.assertAlmostEqual(n_h, 0.3, places=4)

    def test_class_mappings(self):
        """Verify all 6 defect classes + normal are mapped with valid IDs."""
        required_classes = ["crazing", "inclusion", "patches", "pitted_surface", "rolled_in_scale", "scratches", "normal"]
        for c in required_classes:
            self.assertIn(c, CLASS_MAPPING)
            self.assertTrue(0 <= CLASS_MAPPING[c] <= 6)

if __name__ == "__main__":
    unittest.main()
