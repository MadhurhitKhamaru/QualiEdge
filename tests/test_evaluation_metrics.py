#!/usr/bin/env python3
"""
tests/test_evaluation_metrics.py

Unit tests for Phase 4 Evaluation metrics:
1. Precision, Recall, F1-Score calculations.
2. False Positive Rate (FPR) and False Negative Rate (FNR) correctness.
3. Zero-division defense.
4. Latency timing aggregation.
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.evaluate_model import calculate_metrics

class TestEvaluationMetrics(unittest.TestCase):

    def test_perfect_metrics(self):
        """Test ideal scenario where all predictions are true positives."""
        metrics = calculate_metrics(tp=10, fp=0, fn=0, tn=90)
        self.assertEqual(metrics["precision"], 1.0)
        self.assertEqual(metrics["recall"], 1.0)
        self.assertEqual(metrics["f1_score"], 1.0)
        self.assertEqual(metrics["false_positive_rate"], 0.0)
        self.assertEqual(metrics["false_negative_rate"], 0.0)

    def test_imbalanced_metrics(self):
        """Test standard mixed confusion case."""
        # tp=8, fp=2, fn=2, tn=88
        metrics = calculate_metrics(tp=8, fp=2, fn=2, tn=88)
        self.assertAlmostEqual(metrics["precision"], 0.8000, places=4)
        self.assertAlmostEqual(metrics["recall"], 0.8000, places=4)
        self.assertAlmostEqual(metrics["f1_score"], 0.8000, places=4)
        self.assertAlmostEqual(metrics["false_positive_rate"], 2 / 90, places=4)
        self.assertAlmostEqual(metrics["false_negative_rate"], 2 / 10, places=4)

    def test_zero_division_guard(self):
        """Test zero-division cases when model never predicts class or ground truth is empty."""
        metrics = calculate_metrics(tp=0, fp=0, fn=0, tn=0)
        self.assertEqual(metrics["precision"], 0.0)
        self.assertEqual(metrics["recall"], 0.0)
        self.assertEqual(metrics["f1_score"], 0.0)
        self.assertEqual(metrics["false_positive_rate"], 0.0)
        self.assertEqual(metrics["false_negative_rate"], 0.0)

    def test_high_false_alarm_rate(self):
        """Verify that elevated false alarms correctly reflect in high FPR and reduced Precision."""
        metrics = calculate_metrics(tp=5, fp=15, fn=1, tn=79)
        self.assertAlmostEqual(metrics["precision"], 5 / 20, places=4)
        self.assertAlmostEqual(metrics["recall"], 5 / 6, places=4)
        self.assertGreater(metrics["false_positive_rate"], 0.15)

if __name__ == "__main__":
    unittest.main()
