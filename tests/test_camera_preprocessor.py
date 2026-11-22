#!/usr/bin/env python3
"""
tests/test_camera_preprocessor.py

Unit tests for Phase 5 OpenCV Preprocessing & Camera Pipeline:
1. Letterbox coordinate scaling and padding math.
2. Inverse bounding box mapping back to original frame space.
3. Threaded camera initialization and graceful stop.
4. Defect severity color assignment in visualizer.
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cv_pipeline.preprocessor import SteelImagePreprocessor
from cv_pipeline.camera_stream import IndustrialCameraStream
from cv_pipeline.visualizer import DEFECT_SEVERITY_MAP

class TestCameraPreprocessor(unittest.TestCase):

    def setUp(self):
        self.preprocessor = SteelImagePreprocessor(target_size=(640, 640))

    def test_inverse_coordinate_mapping(self):
        """Test that inverse letterbox mapping accurately converts normalized model boxes back to raw frame."""
        orig_shape = (720, 1280) # 16:9 720p frame
        ratio = 640.0 / 1280.0   # 0.5
        pad = (0.0, (640 - 720 * 0.5) / 2) # (0, 140)

        # Model detected box in center: (200, 200, 440, 440)
        x1, y1, x2, y2 = self.preprocessor.map_box_to_raw((200, 200, 440, 440), ratio, pad, orig_shape)
        
        self.assertEqual(x1, 400)
        self.assertEqual(x2, 880)
        self.assertGreater(y1, 0)
        self.assertLess(y2, 720)

    def test_camera_stream_lifecycle(self):
        """Test non-blocking camera start, frame acquisition, and cleanup."""
        stream = IndustrialCameraStream(source=99) # Invalid index forces clean synthetic fallback
        stream.start()
        self.assertTrue(stream.is_running)
        self.assertTrue(stream.is_simulation)
        
        ret, frame = stream.read()
        self.assertIsNotNone(frame)
        self.assertTrue(ret)
        
        stream.stop()
        self.assertFalse(stream.is_running)

    def test_severity_mappings(self):
        """Verify safety-critical defects are mapped to High/Critical."""
        self.assertEqual(DEFECT_SEVERITY_MAP["crazing"], "Critical")
        self.assertEqual(DEFECT_SEVERITY_MAP["inclusion"], "High")
        self.assertEqual(DEFECT_SEVERITY_MAP["pitted_surface"], "High")
        self.assertEqual(DEFECT_SEVERITY_MAP["scratches"], "Medium")
        self.assertEqual(DEFECT_SEVERITY_MAP["normal"], "Normal")

if __name__ == "__main__":
    unittest.main()
