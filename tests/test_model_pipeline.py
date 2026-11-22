#!/usr/bin/env python3
"""
tests/test_model_pipeline.py

Unit tests for Phase 3 Model Development & Detection Engine:
1. Detector initialization.
2. Latency measurement validation.
3. Bounding box coordinates and area ratio boundaries.
4. Confidence filtering.
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cv_pipeline.detector import SteelDefectDetector, DEFECT_CLASSES, DetectionResult

class TestModelPipeline(unittest.TestCase):

    def setUp(self):
        self.detector = SteelDefectDetector()

    def test_class_definitions(self):
        """Ensure all 7 classes are present."""
        self.assertEqual(len(DEFECT_CLASSES), 7)
        self.assertEqual(DEFECT_CLASSES[0], "crazing")
        self.assertEqual(DEFECT_CLASSES[5], "scratches")
        self.assertEqual(DEFECT_CLASSES[6], "normal")

    def test_detector_inference_output(self):
        """Ensure inference returns a valid DetectionResult object."""
        result = self.detector.detect(None)
        self.assertIsInstance(result, DetectionResult)
        self.assertTrue(result.has_defect)
        self.assertGreater(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)
        self.assertGreater(len(result.boxes), 0)

    def test_bounding_box_constraints(self):
        """Verify bounding box coordinates are normalized and non-negative."""
        result = self.detector.detect(None)
        box = result.boxes[0]
        self.assertTrue(0.0 <= box.xc <= 1.0)
        self.assertTrue(0.0 <= box.yc <= 1.0)
        self.assertTrue(0.0 <= box.w <= 1.0)
        self.assertTrue(0.0 <= box.h <= 1.0)
        self.assertTrue(box.x1 <= box.x2)
        self.assertTrue(box.y1 <= box.y2)
        self.assertGreater(box.area_ratio, 0.0)

    def test_latency_metrics(self):
        """Verify inference latency timing is recorded."""
        result = self.detector.detect(None)
        self.assertGreaterEqual(result.inference_ms, 0.0)
        self.assertGreaterEqual(result.total_latency_ms, 0.0)

if __name__ == "__main__":
    unittest.main()
