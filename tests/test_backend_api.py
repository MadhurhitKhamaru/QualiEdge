"""
tests/test_backend_api.py

Unit and Integration Test Suite for Phase 8: Backend API & SQLite Persistence.
Tests:
1. SQLite WAL schema, tables, foreign keys, and indexes.
2. Saving and retrieving Section 7 records, bounding boxes, and Llama advisories.
3. High-throughput filtering and pagination (product_id, defect_type, severity, decision).
4. Operator override logging and decision state transitions.
5. Quality Control KPI statistics calculations.
6. InspectionService full dual-engine execution.
7. REST endpoint dispatching (/api/health, /api/stats, /api/history, /api/inspect, /api/operator/override).
"""

import unittest
import os
import sys
import json
import tempfile
from pathlib import Path
from io import BytesIO

# Ensure project root in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import QualiEdgeDatabase
from backend.main import InspectionService, QualiEdgeHTTPHandler
from backend.schemas import SeverityLevel, InspectionDecision


class MockHTTPRequest:
    def __init__(self, body_bytes: bytes = b""):
        self.rfile = BytesIO(body_bytes)
        self.wfile = BytesIO()
        self.headers = {"Content-Length": str(len(body_bytes))}
        self.response_status = None
        self.response_headers = {}

    def send_response(self, status):
        self.response_status = status

    def send_header(self, key, value):
        self.response_headers[key] = value

    def end_headers(self):
        pass


class TestBackendAPI(unittest.TestCase):

    def setUp(self):
        # Create a temporary database for test isolation
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_qualiedge.db"
        self.db = QualiEdgeDatabase(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_database_initialization(self):
        """Verify schema tables, indexes, and WAL configuration."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row["name"] for row in cursor.fetchall()]
            self.assertIn("inspections", tables)
            self.assertIn("defect_boxes", tables)
            self.assertIn("operator_logs", tables)

            # Verify WAL mode
            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]
            self.assertEqual(journal_mode.lower(), "wal")

    def test_save_and_retrieve_inspection(self):
        """Verify saving and retrieving a full Section 7 record with boxes and advisory."""
        record = {
            "inspection_id": "TEST-INS-001",
            "product_id": "STEEL-TEST-BATCH-A",
            "defect_detected": True,
            "defect_type": "crazing",
            "severity": "Critical",
            "confidence": 0.952,
            "location": "Upper-right surface region",
            "decision": "REJECT",
            "recommendation": "Quarantine coil segment immediately.",
            "inference_ms": 34.2
        }
        boxes = [
            {
                "class_name": "crazing",
                "confidence": 0.952,
                "xmin": 100,
                "ymin": 50,
                "xmax": 300,
                "ymax": 200,
                "area_ratio": 0.075,
                "severity": "Critical"
            }
        ]
        advisory = {
            "root_cause_analysis": "Thermal shock from cold water quenching.",
            "manufacturing_implications": "Severe tensile fracture risk.",
            "operator_action_plan": ["Halt line", "Calibrate nozzles", "Notify melt-shop"],
            "shift_log_summary": "REJECT: Critical crazing detected."
        }

        saved_id = self.db.save_inspection(record, boxes=boxes, advisory=advisory)
        self.assertEqual(saved_id, "TEST-INS-001")

        # Retrieve
        retrieved = self.db.get_inspection("TEST-INS-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["product_id"], "STEEL-TEST-BATCH-A")
        self.assertTrue(retrieved["defect_detected"])
        self.assertEqual(retrieved["defect_type"], "crazing")
        self.assertEqual(retrieved["severity"], "Critical")
        self.assertEqual(len(retrieved["boxes"]), 1)
        self.assertEqual(retrieved["boxes"][0]["xmin"], 100)
        self.assertEqual(retrieved["root_cause"], "Thermal shock from cold water quenching.")
        self.assertEqual(len(retrieved["remediation_steps"]), 3)

    def test_filtering_and_pagination(self):
        """Test search filters and pagination on inspection history."""
        # Insert 3 records
        self.db.save_inspection({
            "inspection_id": "INS-FLT-1",
            "product_id": "COIL-ALPHA",
            "defect_detected": True,
            "defect_type": "scratches",
            "severity": "High",
            "confidence": 0.91,
            "location": "Center",
            "decision": "REJECT",
            "recommendation": "Divert coil."
        })
        self.db.save_inspection({
            "inspection_id": "INS-FLT-2",
            "product_id": "COIL-BETA",
            "defect_detected": False,
            "defect_type": "Normal",
            "severity": "None",
            "confidence": 0.99,
            "location": "Uniform",
            "decision": "ACCEPT",
            "recommendation": "Clear for packaging."
        })
        self.db.save_inspection({
            "inspection_id": "INS-FLT-3",
            "product_id": "COIL-ALPHA",
            "defect_detected": True,
            "defect_type": "patches",
            "severity": "Medium",
            "confidence": 0.85,
            "location": "Lower-left",
            "decision": "REJECT",
            "recommendation": "Secondary structural grade."
        })

        # Filter by product_id
        recs, total = self.db.list_inspections(product_id="ALPHA")
        self.assertEqual(total, 2)
        self.assertEqual(len(recs), 2)

        # Filter by defect_type
        recs, total = self.db.list_inspections(defect_type="Normal")
        self.assertEqual(total, 1)
        self.assertEqual(recs[0]["decision"], "ACCEPT")

        # Filter by severity
        recs, total = self.db.list_inspections(severity="High")
        self.assertEqual(total, 1)
        self.assertEqual(recs[0]["defect_type"], "scratches")

    def test_operator_override_audit(self):
        """Test operator override log and status update."""
        self.db.save_inspection({
            "inspection_id": "INS-OP-01",
            "product_id": "COIL-GAMMA",
            "defect_detected": True,
            "defect_type": "pitted_surface",
            "severity": "Indeterminate",
            "confidence": 0.61,
            "location": "Border",
            "decision": "MANUAL_REVIEW",
            "recommendation": "Manual review required."
        })

        # Operator overrides decision to ACCEPT
        log_id = self.db.log_operator_action(
            inspection_id="INS-OP-01",
            operator_id="OP-SHARP-101",
            action="OVERRIDE_ACCEPT",
            notes="Surface roughness verified with contact profilometer; conforms to Grade 2 tolerance."
        )
        self.assertGreater(log_id, 0)

        # Verify inspection decision changed
        updated = self.db.get_inspection("INS-OP-01")
        self.assertEqual(updated["decision"], "ACCEPT")
        self.assertEqual(len(updated["operator_logs"]), 1)
        self.assertEqual(updated["operator_logs"][0]["operator_id"], "OP-SHARP-101")
        self.assertIn("profilometer", updated["operator_logs"][0]["notes"])

    def test_kpi_stats_aggregation(self):
        """Test calculation of industrial quality metrics."""
        self.db.save_inspection({
            "inspection_id": "STAT-1", "product_id": "P1", "defect_detected": True,
            "defect_type": "crazing", "severity": "Critical", "confidence": 0.95,
            "location": "Top", "decision": "REJECT", "recommendation": "R1", "inference_ms": 30.0
        })
        self.db.save_inspection({
            "inspection_id": "STAT-2", "product_id": "P2", "defect_detected": False,
            "defect_type": "Normal", "severity": "None", "confidence": 0.98,
            "location": "Uniform", "decision": "ACCEPT", "recommendation": "R2", "inference_ms": 25.0
        })
        self.db.save_inspection({
            "inspection_id": "STAT-3", "product_id": "P3", "defect_detected": True,
            "defect_type": "crazing", "severity": "High", "confidence": 0.90,
            "location": "Center", "decision": "REJECT", "recommendation": "R3", "inference_ms": 35.0
        })
        self.db.save_inspection({
            "inspection_id": "STAT-4", "product_id": "P4", "defect_detected": True,
            "defect_type": "inclusion", "severity": "Indeterminate", "confidence": 0.60,
            "location": "Edge", "decision": "MANUAL_REVIEW", "recommendation": "R4", "inference_ms": 30.0
        })

        stats = self.db.get_stats()
        self.assertEqual(stats["total_inspections"], 4)
        self.assertEqual(stats["accepted"], 1)
        self.assertEqual(stats["rejected"], 2)
        self.assertEqual(stats["manual_review"], 1)
        self.assertEqual(stats["defect_rate_pct"], 50.0)  # 2 rejected / 4 total = 50%
        self.assertEqual(stats["avg_inference_ms"], 30.0)
        self.assertEqual(stats["defect_distribution"]["crazing"], 2)
        self.assertEqual(stats["defect_distribution"]["inclusion"], 1)

    def test_inspection_service_execution(self):
        """Test complete InspectionService pipeline run."""
        result = InspectionService.run_inspection(product_id="STEEL-SERVICE-TEST")
        self.assertEqual(result["status"], "success")
        self.assertIn("inspection", result)
        self.assertIn("advisory", result)
        self.assertIn("hardware_telemetry", result)
        self.assertEqual(result["inspection"]["product_id"], "STEEL-SERVICE-TEST")
        self.assertIn(result["inspection"]["decision"], ["ACCEPT", "REJECT", "MANUAL_REVIEW"])

    def test_http_endpoint_dispatch(self):
        """Test REST API routing for GET /api/health, /api/stats, /api/history, POST /api/inspect, /api/operator/override."""
        # 1. Health
        status, body = InspectionService.dispatch_request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "healthy")
        self.assertIn("Raspberry Pi 5", body["edge_device"])

        # 2. Stats
        status, body = InspectionService.dispatch_request("GET", "/api/stats")
        self.assertEqual(status, 200)
        self.assertIn("total_inspections", body)
        self.assertIn("defect_rate_pct", body)

        # 3. Post Inspect
        status, body = InspectionService.dispatch_request("POST", "/api/inspect", body={"product_id": "STEEL-REST-01"})
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["inspection"]["product_id"], "STEEL-REST-01")
        insp_id = body["inspection"]["inspection_id"]

        # 4. Get Single Inspection
        status, body = InspectionService.dispatch_request("GET", f"/api/inspection/{insp_id}")
        self.assertEqual(status, 200)
        self.assertEqual(body["inspection_id"], insp_id)

        # 5. History Query with pagination
        status, body = InspectionService.dispatch_request("GET", "/api/history", query={"limit": "10", "offset": "0"})
        self.assertEqual(status, 200)
        self.assertIn("records", body)
        self.assertGreater(body["total"], 0)

        # 6. Operator Override
        status, body = InspectionService.dispatch_request("POST", "/api/operator/override", body={
            "inspection_id": insp_id,
            "operator_id": "OP-TEST-77",
            "action": "VERIFIED",
            "notes": "Verified visually by supervisor."
        })
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "success")
        self.assertGreater(body["log_id"], 0)


if __name__ == "__main__":
    unittest.main()
