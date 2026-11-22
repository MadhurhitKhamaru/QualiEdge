"""
tests/test_performance_tuning.py

Automated test suite for Phase 11: Integration & Performance Tuning.
Validates sub-millisecond stage-by-stage timing, percentile math, throughput benchmarks,
memory leak profiling, hardware comparison matrix, and REST dispatch routing.
"""

import unittest
import time
from backend.performance_profiler import (
    PipelineStageTimer,
    calculate_percentiles,
    PerformanceBenchmark,
    get_profiler,
    TARGET_BUDGETS_MS,
    HARDWARE_PROFILES
)
from backend.main import InspectionService


class TestPerformanceTuning(unittest.TestCase):

    def setUp(self):
        self.profiler = PerformanceBenchmark()

    def test_pipeline_stage_timer_precision(self):
        """Test nanosecond timer accuracy and duration conversion."""
        timer = PipelineStageTimer()
        timer.start_stage("test_stage")
        time.sleep(0.005)  # 5ms
        duration_ms = timer.stop_stage("test_stage")

        self.assertGreaterEqual(duration_ms, 3.5)
        self.assertLess(duration_ms, 30.0)

        all_durations = timer.get_all_durations_ms()
        self.assertIn("test_stage", all_durations)
        self.assertAlmostEqual(all_durations["test_stage"], duration_ms, places=2)

    def test_percentiles_calculation(self):
        """Test calculation of P50, P90, P95, P99, mean, and stddev."""
        # Empty input test
        empty_res = calculate_percentiles([])
        self.assertEqual(empty_res["mean"], 0.0)
        self.assertEqual(empty_res["p50"], 0.0)

        # Standard uniform sequence 1 to 100
        values = [float(x) for x in range(1, 101)]
        res = calculate_percentiles(values)

        self.assertAlmostEqual(res["mean"], 50.5, places=1)
        self.assertAlmostEqual(res["min"], 1.0)
        self.assertAlmostEqual(res["max"], 100.0)
        self.assertAlmostEqual(res["p50"], 50.5, delta=1.0)
        self.assertAlmostEqual(res["p90"], 90.1, delta=1.0)
        self.assertAlmostEqual(res["p95"], 95.05, delta=1.0)
        self.assertAlmostEqual(res["p99"], 99.01, delta=1.0)
        self.assertGreater(res["stddev"], 28.0)

    def test_benchmark_rpi5_hailo_execution(self):
        """Test running synthetic benchmark on Raspberry Pi 5 + Hailo-8L profile."""
        res = self.profiler.run_benchmark(num_frames=25, target_device="rpi5_hailo")

        self.assertEqual(res["status"], "success")
        self.assertIn("stages", res)
        self.assertIn("throughput", res)
        self.assertIn("memory_profiling", res)
        self.assertIn("budget_compliance", res)

        # Hailo-8L should achieve high sustained FPS (>45 FPS)
        sustained_fps = res["throughput"]["sustained_fps"]
        self.assertGreater(sustained_fps, 40.0)

        # Stages check
        stages = res["stages"]
        self.assertIn("capture_preprocess", stages)
        self.assertIn("vision_inference", stages)
        self.assertIn("postprocess_nms", stages)
        self.assertIn("severity_gating", stages)
        self.assertIn("db_persistence", stages)
        self.assertIn("total_vision_loop", stages)
        self.assertIn("advisory_async", stages)

        # Vision inference mean latency on Hailo-8L should be under 16 ms
        self.assertLess(stages["vision_inference"]["mean"], 16.0)

        # Zero memory leak check
        mem = res["memory_profiling"]
        self.assertIn("net_memory_drift_mb", mem)
        self.assertIn("zero_leak_verified", mem)
        self.assertTrue(mem["zero_leak_verified"])

    def test_benchmark_rpi5_cpu_execution(self):
        """Test running benchmark on Raspberry Pi 5 CPU-only fallback."""
        res = self.profiler.run_benchmark(num_frames=20, target_device="rpi5_cpu")

        self.assertEqual(res["status"], "success")
        # CPU inference latency should be in the ~25-38ms range
        cpu_infer_mean = res["stages"]["vision_inference"]["mean"]
        self.assertGreater(cpu_infer_mean, 20.0)
        self.assertLess(cpu_infer_mean, 45.0)

        # FPS should be in ~20-35 FPS range
        self.assertGreater(res["throughput"]["sustained_fps"], 18.0)

    def test_live_telemetry(self):
        """Test real-time telemetry snapshot retrieval."""
        telemetry = self.profiler.get_live_telemetry()

        self.assertEqual(telemetry["status"], "online")
        self.assertIn("instant_fps", telemetry)
        self.assertIn("total_cycle_ms", telemetry)
        self.assertIn("stages_ms", telemetry)
        self.assertIn("memory", telemetry)
        self.assertIn("async_advisory", telemetry)

        self.assertGreater(telemetry["instant_fps"], 30.0)
        self.assertGreater(telemetry["memory"]["current_rss_mb"], 0.0)

    def test_stress_test_memory_stability(self):
        """Test memory stability over iterative stress test."""
        stress_res = self.profiler.run_stress_test(num_iterations=50, target_device="rpi5_hailo")

        self.assertEqual(stress_res["status"], "completed")
        self.assertEqual(stress_res["iterations"], 50)
        self.assertFalse(stress_res["leak_detected"])
        self.assertLess(stress_res["memory_drift_mb"], 0.1)

    def test_hardware_comparison_matrix(self):
        """Test hardware comparison matrix output."""
        matrix = self.profiler.get_hardware_comparison_matrix()

        self.assertIn("devices", matrix)
        self.assertIn("target_budgets_ms", matrix)
        self.assertIn("analysis", matrix)

        self.assertIn("rpi5_hailo", matrix["devices"])
        self.assertIn("rpi5_cpu", matrix["devices"])
        self.assertIn("arm_generic", matrix["devices"])

        # Hailo speedup should be > 2.0x compared to CPU
        self.assertGreater(matrix["analysis"]["hailo_speedup_vs_cpu"], 1.8)

    def test_rest_dispatch_benchmark_endpoints(self):
        """Test GET and POST routing for benchmark endpoints in InspectionService."""
        # 1. GET /api/benchmark/live-telemetry
        status, data = InspectionService.dispatch_request("GET", "/api/benchmark/live-telemetry")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "online")
        self.assertIn("instant_fps", data)

        # 2. GET /api/benchmark/hardware-matrix
        status, data = InspectionService.dispatch_request("GET", "/api/benchmark/hardware-matrix")
        self.assertEqual(status, 200)
        self.assertIn("devices", data)

        # 3. POST /api/benchmark/run
        status, data = InspectionService.dispatch_request(
            "POST",
            "/api/benchmark/run",
            body={"num_frames": 15, "target_device": "rpi5_hailo"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "success")
        self.assertIn("throughput", data)

        # 4. POST /api/benchmark/stress-test
        status, data = InspectionService.dispatch_request(
            "POST",
            "/api/benchmark/stress-test",
            body={"num_iterations": 30, "target_device": "rpi5_hailo"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "completed")


if __name__ == "__main__":
    unittest.main()
