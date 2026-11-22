"""
tests/test_technical_report.py

Automated test suite for Phase 13: Technical Report, IEEE Paper Generator,
Defense Checklist, and Video Demonstration Script for the Bharat AI SoC Challenge 2026–27.
"""

import unittest
from backend.technical_report import TechnicalReportService, get_report_service
from backend.main import InspectionService


class TestTechnicalReport(unittest.TestCase):

    def setUp(self):
        self.report_svc = TechnicalReportService()

    def test_ieee_paper_metadata(self):
        """Test IEEE paper metadata structure, title, and keywords."""
        meta = self.report_svc.get_ieee_paper_metadata()

        self.assertIn("title", meta)
        self.assertIn("QualiEdge", meta["title"])
        self.assertIn("Bharat AI SoC Challenge", meta["conference"])
        self.assertIn("keywords", meta)
        self.assertIn("NEU-DET", meta["keywords"])
        self.assertIn("Hailo-8L NPU", meta["keywords"])
        self.assertIn("ExecuTorch", meta["keywords"])

    def test_ieee_paper_full_text(self):
        """Test IEEE paper full text contains required formal scientific sections."""
        full_text = self.report_svc.get_ieee_paper_full_text()

        self.assertIn("### Abstract", full_text)
        self.assertIn("### I. Introduction", full_text)
        self.assertIn("### II. Heterogeneous Edge Architecture", full_text)
        self.assertIn("### III. Computer Vision Pipeline", full_text)
        self.assertIn("### IV. Section 7 Fail-Safe Severity Gating", full_text)
        self.assertIn("### V. Decoupled On-Device Llama 3.2 Advisory Engine", full_text)
        self.assertIn("### VI. Performance Tuning & Verification Results", full_text)
        self.assertIn("### VII. Conclusion & Challenge Compliance", full_text)

        # Quantitative metrics present in text
        self.assertIn("0.942", full_text) # mAP@50
        self.assertIn("11.45 ms", full_text) # Hailo latency
        self.assertIn("58.8 sustained FPS", full_text) # FPS
        self.assertIn("0.000 MB", full_text) # zero drift

    def test_defense_checklist(self):
        """Test defense rubrics, scoring weights, and hardware certification."""
        checklist = self.report_svc.get_defense_checklist()

        self.assertEqual(checklist["challenge_name"], "Bharat AI SoC Challenge 2026–27")
        self.assertGreaterEqual(checklist["overall_score"], 95.0)
        self.assertEqual(len(checklist["rubrics"]), 6)

        # Rubrics verification
        rubric_ids = [r["id"] for r in checklist["rubrics"]]
        self.assertEqual(rubric_ids, ["R1", "R2", "R3", "R4", "R5", "R6"])

        # Hardware cert
        cert = checklist["hardware_certification"]
        self.assertTrue(cert["compliance_verified"])
        self.assertIn("Broadcom BCM2712", cert["tested_soc"])

    def test_video_demo_script(self):
        """Test 3-minute video presentation cues, scenes, and duration."""
        script = self.report_svc.get_video_demo_script()

        self.assertEqual(script["target_duration_seconds"], 180)
        scenes = script["scenes"]
        self.assertEqual(len(scenes), 4)

        for s in scenes:
            self.assertIn("scene_number", s)
            self.assertIn("timestamp", s)
            self.assertIn("title", s)
            self.assertIn("visual_cue", s)
            self.assertIn("speaker_notes", s)
            self.assertIn("key_metric", s)

    def test_rest_dispatch_reports(self):
        """Test REST API dispatch routing for Phase 13 report endpoints."""
        # 1. IEEE paper
        status, data = InspectionService.dispatch_request("GET", "/api/reports/ieee-paper")
        self.assertEqual(status, 200)
        self.assertIn("metadata", data)
        self.assertIn("full_text", data)

        # 2. Defense checklist
        status, data = InspectionService.dispatch_request("GET", "/api/reports/defense-checklist")
        self.assertEqual(status, 200)
        self.assertIn("rubrics", data)
        self.assertGreaterEqual(data["overall_score"], 90.0)

        # 3. Video demo script
        status, data = InspectionService.dispatch_request("GET", "/api/reports/demo-script")
        self.assertEqual(status, 200)
        self.assertEqual(data["target_duration_seconds"], 180)


if __name__ == "__main__":
    unittest.main()
