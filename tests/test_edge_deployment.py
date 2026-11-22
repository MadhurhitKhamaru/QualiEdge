"""
tests/test_edge_deployment.py

Automated test suite for Phase 12: Raspberry Pi 5 & Hailo-8L Edge Deployment Engine.
Validates thermal tracking, throttling detection, PCIe M.2 accelerator health,
Arm64 Cortex-A76 core affinity, governor switching, and systemd production service generation.
"""

import unittest
from backend.edge_deployment import EdgeDeploymentManager, get_deployment_manager
from backend.main import InspectionService


class TestEdgeDeployment(unittest.TestCase):

    def setUp(self):
        self.mgr = EdgeDeploymentManager()

    def test_thermal_telemetry(self):
        """Test CPU and NPU thermal readings, fan curve, and headroom."""
        thermal = self.mgr.get_thermal_telemetry()

        self.assertIn("cpu_temp_c", thermal)
        self.assertIn("hailo_temp_c", thermal)
        self.assertIn("fan", thermal)
        self.assertIn("frequencies_mhz", thermal)
        self.assertIn("throttling_status", thermal)
        self.assertIn("thermal_headroom_c", thermal)

        # Realistic temperatures on RPi 5 with Active Cooler
        self.assertGreater(thermal["cpu_temp_c"], 30.0)
        self.assertLess(thermal["cpu_temp_c"], 90.0)
        self.assertGreater(thermal["fan"]["rpm"], 1000)
        self.assertFalse(thermal["throttling_status"]["under_voltage_detected"])

    def test_hailo_status(self):
        """Test Hailo-8L PCIe link status, rated TOPS, and turnaround latency."""
        hailo = self.mgr.get_hailo_status()

        self.assertTrue(hailo["device_connected"])
        self.assertEqual(hailo["compute"]["rated_tops"], 13.0)
        self.assertIn("pcie_link", hailo)
        self.assertEqual(hailo["pcie_link"]["generation"], "PCIe Gen 2.0")
        self.assertEqual(hailo["pcie_link"]["bandwidth_theoretical_mbps"], 500.0)

        turnaround = hailo["turnaround_breakdown_ms"]
        self.assertIn("host_to_device_dma_ms", turnaround)
        self.assertIn("npu_execution_ms", turnaround)
        self.assertIn("device_to_host_dma_ms", turnaround)
        self.assertLess(turnaround["total_turnaround_ms"], 15.0)

    def test_core_affinities(self):
        """Test 4x Cortex-A76 core partitioning and task assignments."""
        affinities = self.mgr.get_core_affinities()

        self.assertEqual(affinities["total_cores"], 4)
        self.assertEqual(affinities["soc"], "Broadcom BCM2712 (16nm FinFET)")
        cores = affinities["core_assignments"]
        self.assertIn("core_0", cores)
        self.assertIn("core_1", cores)
        self.assertIn("core_2", cores)
        self.assertIn("core_3", cores)

        # Core 0 should be assigned to V4L2/CLAHE
        self.assertIn("V4L2", cores["core_0"]["assigned_task"])
        # Core 3 should be assigned to ExecuTorch
        self.assertIn("ExecuTorch", cores["core_3"]["assigned_task"])

    def test_governor_setting(self):
        """Test setting and validating CPU frequency scaling governor."""
        res = self.mgr.set_governor("performance")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["governor"], "performance")

        res_sched = self.mgr.set_governor("schedutil")
        self.assertEqual(res_sched["status"], "success")
        self.assertEqual(res_sched["governor"], "schedutil")

        res_invalid = self.mgr.set_governor("invalid_gov")
        self.assertEqual(res_invalid["status"], "error")

    def test_systemd_and_boot_config_generation(self):
        """Test generation of production systemd service and config.txt."""
        systemd = self.mgr.generate_systemd_service()
        self.assertIn("[Unit]", systemd)
        self.assertIn("CPUAffinity=0 1 2 3", systemd)
        self.assertIn("WatchdogSec=10s", systemd)
        self.assertIn("ExecStart=", systemd)

        boot_cfg = self.mgr.generate_rpi_boot_config()
        self.assertIn("dtparam=pciex1", boot_cfg)
        self.assertIn("dtparam=pciex1_gen=2", boot_cfg)
        self.assertIn("arm_64bit=1", boot_cfg)

    def test_deployment_verification(self):
        """Test production readiness verification checklist."""
        verif = self.mgr.run_deployment_verification()

        self.assertTrue(verif["all_passed"])
        self.assertEqual(len(verif["checklist"]), 7)
        self.assertIn("Production Ready", verif["overall_readiness"])

    def test_rest_dispatch_deployment_endpoints(self):
        """Test REST API dispatch routing for Phase 12 endpoints."""
        # 1. Thermal
        status, data = InspectionService.dispatch_request("GET", "/api/deployment/thermal")
        self.assertEqual(status, 200)
        self.assertIn("cpu_temp_c", data)

        # 2. Hailo
        status, data = InspectionService.dispatch_request("GET", "/api/deployment/hailo")
        self.assertEqual(status, 200)
        self.assertEqual(data["compute"]["rated_tops"], 13.0)

        # 3. Cores
        status, data = InspectionService.dispatch_request("GET", "/api/deployment/cores")
        self.assertEqual(status, 200)
        self.assertEqual(data["total_cores"], 4)

        # 4. Verification
        status, data = InspectionService.dispatch_request("GET", "/api/deployment/verification")
        self.assertEqual(status, 200)
        self.assertTrue(data["all_passed"])

        # 5. Systemd
        status, data = InspectionService.dispatch_request("GET", "/api/deployment/systemd")
        self.assertEqual(status, 200)
        self.assertIn("systemd_unit", data)

        # 6. Boot config
        status, data = InspectionService.dispatch_request("GET", "/api/deployment/boot-config")
        self.assertEqual(status, 200)
        self.assertIn("boot_config", data)

        # 7. Governor POST
        status, data = InspectionService.dispatch_request(
            "POST",
            "/api/deployment/governor",
            body={"governor": "performance"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["governor"], "performance")


if __name__ == "__main__":
    unittest.main()
