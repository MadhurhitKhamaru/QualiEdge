"""
tests/test_history_reports.py

Unit tests for Phase 10: Inspection History, Advanced Filtering,
Shift Quality Reports, ISO 9001 Certificate Generation, and SQLite Maintenance.
"""

import unittest
import tempfile
import os
import json
import csv
import io
from pathlib import Path
from backend.database import QualiEdgeDatabase
from backend.main import InspectionService


class TestHistoryAndReports(unittest.TestCase):
    """Tests SQLite persistence query filters, shift reports, and certificate generation."""

    def setUp(self):
        # Create a temporary database for isolated testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_qualiedge.db"
        self.db = QualiEdgeDatabase(db_path=self.db_path)

        # Seed known test records
        self.records = [
            {
                "inspection_id": "TEST-INS-001",
                "product_id": "COIL-A101",
                "timestamp": "2026-11-03T01:00:00Z",
                "defect_detected": True,
                "defect_type": "crazing",
                "severity": "Critical",
                "confidence": 0.95,
                "location": "Upper edge zone",
                "decision": "REJECT",
                "recommendation": "Quarantine segment immediately.",
                "inference_ms": 35.2
            },
            {
                "inspection_id": "TEST-INS-002",
                "product_id": "COIL-A102",
                "timestamp": "2026-11-03T02:00:00Z",
                "defect_detected": False,
                "defect_type": "Normal",
                "severity": "None",
                "confidence": 0.99,
                "location": "Uniform surface",
                "decision": "ACCEPT",
                "recommendation": "Release to slitting.",
                "inference_ms": 31.0
            },
            {
                "inspection_id": "TEST-INS-003",
                "product_id": "COIL-B201",
                "timestamp": "2026-11-03T03:00:00Z",
                "defect_detected": True,
                "defect_type": "scratches",
                "severity": "High",
                "confidence": 0.88,
                "location": "Central longitudinal lane",
                "decision": "REJECT",
                "recommendation": "Polish pinch rolls.",
                "inference_ms": 36.5
            },
            {
                "inspection_id": "TEST-INS-004",
                "product_id": "COIL-B202",
                "timestamp": "2026-11-03T04:00:00Z",
                "defect_detected": True,
                "defect_type": "patches",
                "severity": "Medium",
                "confidence": 0.72,
                "location": "Center-left zone",
                "decision": "MANUAL_REVIEW",
                "recommendation": "Operator visual check.",
                "inference_ms": 38.0
            },
            {
                "inspection_id": "TEST-INS-005",
                "product_id": "COIL-C301",
                "timestamp": "2026-11-03T05:00:00Z",
                "defect_detected": False,
                "defect_type": "Normal",
                "severity": "None",
                "confidence": 0.98,
                "location": "Uniform surface",
                "decision": "ACCEPT",
                "recommendation": "Release to downstream line.",
                "inference_ms": 32.4
            }
        ]

        for r in self.records:
            boxes = []
            if r["defect_detected"]:
                boxes.append({
                    "class_name": r["defect_type"],
                    "confidence": r["confidence"],
                    "xmin": 100, "ymin": 100, "xmax": 200, "ymax": 200,
                    "area_ratio": 0.05,
                    "severity": r["severity"]
                })
            self.db.save_inspection(r, boxes=boxes)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_list_inspections_filtering(self):
        """Verify multi-criteria filtering by defect type, severity, decision, and confidence."""
        # 1. Filter by defect type
        records, total = self.db.list_inspections(defect_type="crazing")
        self.assertEqual(total, 1)
        self.assertEqual(records[0]["inspection_id"], "TEST-INS-001")

        # 2. Filter by decision
        records, total = self.db.list_inspections(decision="ACCEPT")
        self.assertEqual(total, 2)

        # 3. Filter by severity
        records, total = self.db.list_inspections(severity="Critical")
        self.assertEqual(total, 1)

        # 4. Filter by confidence range
        records, total = self.db.list_inspections(confidence_min=0.90)
        self.assertEqual(total, 3)  # 0.95, 0.99, 0.98

        records, total = self.db.list_inspections(confidence_min=0.70, confidence_max=0.85)
        self.assertEqual(total, 1)  # 0.72

        # 5. Filter by product ID pattern
        records, total = self.db.list_inspections(product_id="COIL-B")
        self.assertEqual(total, 2)

    def test_list_inspections_sorting_and_pagination(self):
        """Verify sorting order and pagination limits/offsets."""
        # Sort by confidence ascending
        records, total = self.db.list_inspections(sort_by="confidence", order="ASC", limit=2)
        self.assertEqual(len(records), 2)
        self.assertLessEqual(records[0]["confidence"], records[1]["confidence"])
        self.assertAlmostEqual(records[0]["confidence"], 0.72)

        # Pagination offset
        records_p2, _ = self.db.list_inspections(sort_by="confidence", order="ASC", limit=2, offset=2)
        self.assertEqual(len(records_p2), 2)
        self.assertGreaterEqual(records_p2[0]["confidence"], records[1]["confidence"])

    def test_shift_report_metrics(self):
        """Verify ISO 9001 / ASTM A1008 Shift Quality Report statistical aggregates."""
        report = self.db.get_shift_report(shift_name="Morning Shift A")

        self.assertEqual(report["total_inspected"], 5)
        self.assertEqual(report["accepted_count"], 2)
        self.assertEqual(report["rejected_count"], 2)
        self.assertEqual(report["manual_review_count"], 1)

        # First-pass yield: 2 / 5 = 40.0%
        self.assertAlmostEqual(report["first_pass_yield_pct"], 40.0)
        # Scrap rate: 2 / 5 = 40.0%
        self.assertAlmostEqual(report["scrap_rate_pct"], 40.0)
        # Manual rate: 1 / 5 = 20.0%
        self.assertAlmostEqual(report["manual_intervention_rate_pct"], 20.0)

        # Defect breakdown
        self.assertEqual(report["defect_breakdown"].get("crazing"), 1)
        self.assertEqual(report["defect_breakdown"].get("scratches"), 1)
        self.assertEqual(report["defect_breakdown"].get("patches"), 1)

        # With 40% scrap, quality verdict should flag an excursion
        self.assertIn("QUALITY HOLD", report["compliance_verdict"])

    def test_digital_certificate_generation(self):
        """Verify ASTM A1008 Quality Inspection Certificate and SHA-256 cryptographic seal."""
        cert = self.db.get_inspection_certificate("TEST-INS-001")
        self.assertIsNotNone(cert)
        self.assertIn("certificate_id", cert)
        self.assertTrue(cert["certificate_id"].startswith("CERT-TEST-001"))
        self.assertEqual(cert["inspection_record"]["defect_type"], "crazing")
        self.assertEqual(cert["digital_signature"]["hash_algorithm"], "SHA-256")
        self.assertEqual(len(cert["digital_signature"]["seal"]), 64)  # 64 hex characters for SHA-256

        # Non-existent inspection returns None
        bad_cert = self.db.get_inspection_certificate("NON-EXISTENT")
        self.assertIsNone(bad_cert)

    def test_csv_export_format(self):
        """Verify RFC 4180 CSV export headers and data integrity."""
        csv_output = self.db.export_inspections_csv()
        reader = csv.DictReader(io.StringIO(csv_output))
        rows = list(reader)

        self.assertEqual(len(rows), 5)
        self.assertIn("inspection_id", reader.fieldnames)
        self.assertIn("product_id", reader.fieldnames)
        self.assertIn("defect_type", reader.fieldnames)
        self.assertIn("confidence", reader.fieldnames)
        self.assertIn("decision", reader.fieldnames)

        # Filtered CSV export
        filtered_csv = self.db.export_inspections_csv(decision="ACCEPT")
        filtered_rows = list(csv.DictReader(io.StringIO(filtered_csv)))
        self.assertEqual(len(filtered_rows), 2)
        for r in filtered_rows:
            self.assertEqual(r["decision"], "ACCEPT")

    def test_database_maintenance_vacuum_and_stats(self):
        """Verify database maintenance utilities: stats, vacuum, and purge."""
        stats = self.db.get_db_maintenance_stats()
        self.assertEqual(stats["record_counts"]["inspections"], 5)
        self.assertEqual(stats["record_counts"]["defect_boxes"], 3)
        self.assertEqual(stats["journal_mode"], "WAL")
        self.assertGreater(stats["page_count"], 0)

        # Vacuum execution
        vacuum_res = self.db.vacuum_database()
        self.assertEqual(vacuum_res["status"], "SUCCESS")

        # Purge execution (cutoff 30 days should delete 0 records from today)
        purge_res = self.db.purge_records(days_older_than=30)
        self.assertEqual(purge_res["status"], "SUCCESS")
        self.assertEqual(purge_res["deleted_count"], 0)

    def test_inspection_service_rest_dispatch(self):
        """Verify the InspectionService dispatch_request handles Phase 10 API endpoints."""
        # 1. Shift report route
        status, data = InspectionService.dispatch_request("GET", "/api/reports/shift", query={"shift": "Morning Shift"})
        self.assertEqual(status, 200)
        self.assertIn("total_inspected", data)
        self.assertIn("first_pass_yield_pct", data)

        # 2. Database maintenance route
        status, data = InspectionService.dispatch_request("GET", "/api/db/maintenance")
        self.assertEqual(status, 200)
        self.assertIn("journal_mode", data)

        # 3. CSV export route
        status, data = InspectionService.dispatch_request("GET", "/api/history/export")
        self.assertEqual(status, 200)
        self.assertEqual(data["format"], "text/csv")
        self.assertIn("csv", data)

        # 4. Vacuum route
        status, data = InspectionService.dispatch_request("POST", "/api/db/vacuum")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
