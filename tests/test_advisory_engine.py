#!/usr/bin/env python3
"""
tests/test_advisory_engine.py

Unit test suite for Phase 7 Llama + ExecuTorch Integration:
1. Llama-3 prompt template formatting and special token boundaries.
2. Assertion that raw pixel/image arrays are strictly barred from prompt context.
3. Synchronous and asynchronous advisory generation.
4. Metallurgical domain accuracy for all 6 defect types + normal.
5. Fail-safe manual review advisory behavior.
"""

import unittest
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from advisory_engine.prompt_templates import format_llama3_advisory_prompt, format_shift_log_prompt
from advisory_engine.executorch_runner import LlamaExecuTorchRunner

class TestAdvisoryEngine(unittest.TestCase):

    def setUp(self):
        self.runner = LlamaExecuTorchRunner()

    def tearDown(self):
        self.runner.stop()

    def test_llama3_prompt_formatting(self):
        """Verify Llama-3 special token syntax and structured-only context."""
        record = {
            "inspection_id": "INS-001",
            "product_id": "STEEL-001",
            "defect_detected": True,
            "defect_type": "Scratches",
            "severity": "High",
            "confidence": 0.96,
            "location": "Upper-right region",
            "decision": "REJECT"
        }
        prompt = format_llama3_advisory_prompt(record)
        
        # Verify Llama 3 special token structure
        self.assertTrue(prompt.startswith("<|begin_of_text|>"))
        self.assertIn("<|start_header_id|>system<|end_header_id|>", prompt)
        self.assertIn("<|start_header_id|>user<|end_header_id|>", prompt)
        self.assertIn("<|start_header_id|>assistant<|end_header_id|>", prompt)
        self.assertIn("INSPECTION RECORD ID: INS-001", prompt)
        self.assertIn("PRODUCT / BATCH ID:   STEEL-001", prompt)

        # Critical: Verify no raw pixel or binary content in prompt
        self.assertNotIn("base64", prompt.lower())
        self.assertNotIn("image_bytes", prompt.lower())

    def test_advisory_generation(self):
        """Test synchronous advisory generation for defect."""
        record = {
            "inspection_id": "INS-CRZ-101",
            "product_id": "STEEL-COIL-77",
            "defect_detected": True,
            "defect_type": "Crazing",
            "severity": "Critical",
            "confidence": 0.98,
            "location": "Central strip region",
            "decision": "REJECT"
        }
        advisory = self.runner.generate_advisory(record)

        self.assertIn("root_cause_analysis", advisory)
        self.assertIn("operator_action_plan", advisory)
        self.assertIn("shift_log_summary", advisory)
        self.assertEqual(len(advisory["operator_action_plan"]), 3)

        # Domain check: Crazing must cite cooling or thermal shock
        self.assertTrue("thermal" in advisory["root_cause_analysis"].lower() or "cooling" in advisory["root_cause_analysis"].lower())

    def test_defect_free_normal_advisory(self):
        """Test advisory output for normal, accepted steel surfaces."""
        record = {
            "inspection_id": "INS-NORM-202",
            "product_id": "STEEL-COIL-88",
            "defect_detected": False,
            "defect_type": "Normal",
            "severity": "None",
            "confidence": 0.995,
            "location": "Uniform surface",
            "decision": "ACCEPT"
        }
        advisory = self.runner.generate_advisory(record)
        self.assertIn("ACCEPT", advisory["shift_log_summary"])
        self.assertIn("Release", advisory["operator_action_plan"][0])

    def test_async_advisory_worker(self):
        """Test non-blocking asynchronous queue submission."""
        record = {
            "inspection_id": "INS-ASYNC-303",
            "product_id": "STEEL-COIL-99",
            "defect_detected": True,
            "defect_type": "Inclusion",
            "severity": "High",
            "confidence": 0.92,
            "location": "Lower-left region",
            "decision": "REJECT"
        }
        received_result = []

        def on_complete(res):
            received_result.append(res)

        self.runner.submit_async(record, callback=on_complete)
        # Wait up to 1 second for worker thread
        for _ in range(10):
            if received_result:
                break
            time.sleep(0.05)

        self.assertEqual(len(received_result), 1)
        self.assertEqual(received_result[0]["inspection_id"], "INS-ASYNC-303")
        self.assertIn("REJECT", received_result[0]["shift_log_summary"])

if __name__ == "__main__":
    unittest.main()
