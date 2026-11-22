#!/usr/bin/env python3
"""
tests/test_severity_schema.py

Unit test suite for Phase 6 Defect Severity Assessment & Pydantic Schema:
1. Spatial location quadrant translation.
2. Defect-free acceptance gating.
3. Low-confidence fail-safe review gating.
4. Schema conformance to Section 7 required fields.
"""

import unittest
import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cv_pipeline.severity_engine import SeverityAssessmentEngine, resolve_spatial_location
from backend.schemas import StructuredInspectionRecord, SeverityLevel, InspectionDecision

class TestSeverityAndSchema(unittest.TestCase):

    def setUp(self):
        self.engine = SeverityAssessmentEngine(confidence_cutoff=0.65)

    def test_spatial_location_mapping(self):
        """Test normalized coordinate to descriptive zone mapping."""
        self.assertEqual(resolve_spatial_location(0.85, 0.15), "Upper-right region")
        self.assertEqual(resolve_spatial_location(0.15, 0.15), "Upper-left region")
        self.assertEqual(resolve_spatial_location(0.15, 0.85), "Lower-left region")
        self.assertEqual(resolve_spatial_location(0.85, 0.85), "Lower-right region")
        self.assertEqual(resolve_spatial_location(0.50, 0.50), "Central strip region")

    def test_defect_free_acceptance(self):
        """Test empty box list generates ACCEPT decision with SeverityLevel.NONE."""
        record = self.engine.assess(boxes=[], product_id="STEEL-NORMAL-01")
        self.assertFalse(record.defect_detected)
        self.assertEqual(record.decision, InspectionDecision.ACCEPT)
        self.assertEqual(record.severity, SeverityLevel.NONE)
        self.assertIn("passes", record.recommendation.lower())

    def test_low_confidence_failsafe(self):
        """Test defect with confidence below 0.65 is routed to MANUAL_REVIEW."""
        box = [{
            "class_id": 0,
            "class_name": "crazing",
            "confidence": 0.54,
            "xc": 0.40,
            "yc": 0.40,
            "w": 0.10,
            "h": 0.10,
            "x1": 40, "y1": 40, "x2": 50, "y2": 50,
            "area_ratio": 0.01
        }]
        record = self.engine.assess(box, product_id="STEEL-UNCERTAIN-02")
        self.assertTrue(record.defect_detected)
        self.assertEqual(record.decision, InspectionDecision.MANUAL_REVIEW)
        self.assertEqual(record.severity, SeverityLevel.INDETERMINATE)
        self.assertIn("hold", record.recommendation.lower())

    def test_section7_schema_keys(self):
        """Verify strict adherence to Section 7 output payload structure."""
        box = [{
            "class_id": 5,
            "class_name": "scratches",
            "confidence": 0.96,
            "xc": 0.85,
            "yc": 0.15,
            "w": 0.20,
            "h": 0.05,
            "x1": 500, "y1": 80, "x2": 620, "y2": 110,
            "area_ratio": 0.01
        }]
        record = self.engine.assess(box, product_id="STEEL-001", inspection_id="INS-001")
        dump = json.loads(record.model_dump_json())

        required_keys = [
            "inspection_id",
            "product_id",
            "defect_detected",
            "defect_type",
            "severity",
            "confidence",
            "location",
            "decision",
            "recommendation",
            "timestamp"
        ]

        for k in required_keys:
            self.assertIn(k, dump)

        self.assertEqual(dump["inspection_id"], "INS-001")
        self.assertEqual(dump["product_id"], "STEEL-001")
        self.assertTrue(dump["defect_detected"])
        self.assertEqual(dump["defect_type"], "Scratches")
        self.assertEqual(dump["confidence"], 0.96)
        self.assertEqual(dump["location"], "Upper-right region")
        self.assertEqual(dump["decision"], "REJECT")

if __name__ == "__main__":
    unittest.main()
