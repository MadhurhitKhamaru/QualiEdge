"""
backend/main.py

QualiEdge Industrial Quality Control REST API & Edge Inference Server.
Coordinates OpenCV camera streams, YOLOv8n defect detection, Section 7 Severity Assessment,
ExecuTorch Llama 3.2 on-device metallurgical advisory, and SQLite persistence.

Supports both FastAPI/Uvicorn (when installed on Raspberry Pi 5) and built-in Python
HTTP engine for lightweight, zero-dependency edge runtime.
"""

import os
import sys
import json
import time
import uuid
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

# Ensure project root in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import QualiEdgeDatabase
from backend.schemas import SeverityLevel, InspectionDecision, StructuredInspectionRecord
from cv_pipeline.detector import SteelDefectDetector, DEFECT_CLASSES
from cv_pipeline.severity_engine import SeverityAssessmentEngine
from cv_pipeline.camera_stream import IndustrialCameraStream
from advisory_engine.executorch_runner import LlamaExecuTorchRunner
from backend.performance_profiler import get_profiler, PerformanceBenchmark
from backend.edge_deployment import get_deployment_manager, EdgeDeploymentManager
from backend.technical_report import get_report_service, TechnicalReportService

# Global singletons
_db = QualiEdgeDatabase()
_db.seed_demo_data()

_detector = SteelDefectDetector()
_severity_engine = SeverityAssessmentEngine()
_advisory_runner = LlamaExecuTorchRunner()
_camera_stream = IndustrialCameraStream()
_profiler = get_profiler()
_deployment_mgr = get_deployment_manager()
_report_service = get_report_service()

# Check for FastAPI availability
try:
    from fastapi import FastAPI, Request, Response, HTTPException, Query
    from fastapi.responses import JSONResponse, StreamingResponse
    from fastapi.middleware.cors import CORSMiddleware
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    FastAPI = None


class InspectionService:
    """
    Coordinates the dual-engine edge inspection pipeline:
    Camera Frame -> CV Detection -> Severity Assessment -> Llama Advisory -> SQLite.
    """

    @staticmethod
    def run_inspection(product_id: Optional[str] = None, image_bytes: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Executes a complete inspection cycle.
        """
        product_id = product_id or f"STEEL-COIL-{int(time.time()) % 10000:04d}"
        inspection_id = f"INS-{int(time.time())}-{uuid.uuid4().hex[:6].upper()}"

        start_time = time.time()

        # 1. Acquire Frame (from camera stream or synthetic simulation)
        frame = _camera_stream.read()
        if frame is None:
            # Generate synthetic test frame
            frame = _camera_stream._generate_synthetic_steel_frame()

        # 2. Vision Inference (YOLO / HailoRT)
        detection_result = _detector.detect(frame)
        box_objects = getattr(detection_result, "boxes", [])
        raw_boxes = [b.__dict__ if hasattr(b, "__dict__") else b for b in box_objects]

        # 3. Severity & Decision Engine (Section 7 Conformant)
        inference_ms = round((time.time() - start_time) * 1000.0, 2)
        structured_record = _severity_engine.assess(
            boxes=raw_boxes,
            product_id=product_id,
            inspection_id=inspection_id,
            inference_ms=inference_ms
        )

        record_dict = structured_record.model_dump()

        # 4. Llama 3.2 ExecuTorch Advisory (receives strictly structured facts)
        advisory = _advisory_runner.generate_advisory(record_dict)

        # 5. Persist to SQLite
        _db.save_inspection(
            record=record_dict,
            boxes=raw_boxes,
            advisory=advisory,
            image_path=None
        )

        # Assemble full response
        response_payload = {
            "status": "success",
            "inspection": record_dict,
            "boxes": raw_boxes,
            "advisory": advisory,
            "hardware_telemetry": {
                "target_device": "Raspberry Pi 5 (Arm Cortex-A76)",
                "acceleration": "XNNPACK 4-bit / Optional Hailo-8L NPU",
                "total_pipeline_ms": inference_ms,
                "offline_status": "Strictly Local / Edge Offline"
            }
        }

        return response_payload

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        return _db.get_stats()

    @staticmethod
    def get_history(
        limit: int = 50,
        offset: int = 0,
        product_id: Optional[str] = None,
        defect_type: Optional[str] = None,
        severity: Optional[str] = None,
        decision: Optional[str] = None,
        confidence_min: Optional[float] = None,
        confidence_max: Optional[float] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sort_by: str = "timestamp",
        order: str = "DESC"
    ) -> Dict[str, Any]:
        records, total = _db.list_inspections(
            limit=limit,
            offset=offset,
            product_id=product_id,
            defect_type=defect_type,
            severity=severity,
            decision=decision,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            start_date=start_date,
            end_date=end_date,
            sort_by=sort_by,
            order=order
        )
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "records": records
        }

    @staticmethod
    def get_inspection(inspection_id: str) -> Optional[Dict[str, Any]]:
        return _db.get_inspection(inspection_id)

    @staticmethod
    def get_shift_report(shift_name: str = "Current Shift", start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        return _db.get_shift_report(shift_name=shift_name, start_date=start_date, end_date=end_date)

    @staticmethod
    def get_inspection_certificate(inspection_id: str) -> Optional[Dict[str, Any]]:
        return _db.get_inspection_certificate(inspection_id)

    @staticmethod
    def export_csv(
        product_id: Optional[str] = None,
        defect_type: Optional[str] = None,
        severity: Optional[str] = None,
        decision: Optional[str] = None,
        confidence_min: Optional[float] = None,
        confidence_max: Optional[float] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 1000
    ) -> str:
        return _db.export_inspections_csv(
            product_id=product_id,
            defect_type=defect_type,
            severity=severity,
            decision=decision,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

    @staticmethod
    def get_db_maintenance() -> Dict[str, Any]:
        return _db.get_db_maintenance_stats()

    @staticmethod
    def vacuum_db() -> Dict[str, Any]:
        return _db.vacuum_database()

    @staticmethod
    def purge_db(days_older_than: int = 30) -> Dict[str, Any]:
        return _db.purge_records(days_older_than=days_older_than)

    @staticmethod
    def operator_override(inspection_id: str, operator_id: str, action: str, notes: Optional[str] = None) -> Dict[str, Any]:
        row_id = _db.log_operator_action(inspection_id, operator_id, action, notes)
        updated = _db.get_inspection(inspection_id)
        return {
            "status": "success",
            "log_id": row_id,
            "inspection": updated
        }

    @staticmethod
    def run_benchmark(
        num_frames: int = 100,
        target_device: str = "rpi5_hailo",
        simulate_heavy_load: bool = False
    ) -> Dict[str, Any]:
        return _profiler.run_benchmark(
            num_frames=num_frames,
            target_device=target_device,
            simulate_heavy_load=simulate_heavy_load
        )

    @staticmethod
    def get_benchmark_telemetry() -> Dict[str, Any]:
        return _profiler.get_live_telemetry()

    @staticmethod
    def run_stress_test(
        num_iterations: int = 250,
        target_device: str = "rpi5_hailo"
    ) -> Dict[str, Any]:
        return _profiler.run_stress_test(
            num_iterations=num_iterations,
            target_device=target_device
        )

    @staticmethod
    def get_hardware_comparison_matrix() -> Dict[str, Any]:
        return _profiler.get_hardware_comparison_matrix()

    @staticmethod
    def get_thermal_telemetry() -> Dict[str, Any]:
        return _deployment_mgr.get_thermal_telemetry()

    @staticmethod
    def get_hailo_status() -> Dict[str, Any]:
        return _deployment_mgr.get_hailo_status()

    @staticmethod
    def get_core_affinities() -> Dict[str, Any]:
        return _deployment_mgr.get_core_affinities()

    @staticmethod
    def set_cpu_governor(governor: str) -> Dict[str, Any]:
        return _deployment_mgr.set_governor(governor)

    @staticmethod
    def get_systemd_service() -> str:
        return _deployment_mgr.generate_systemd_service()

    @staticmethod
    def get_boot_config() -> str:
        return _deployment_mgr.generate_rpi_boot_config()

    @staticmethod
    def get_deployment_verification() -> Dict[str, Any]:
        return _deployment_mgr.run_deployment_verification()

    @staticmethod
    def get_ieee_paper() -> Dict[str, Any]:
        return {
            "metadata": _report_service.get_ieee_paper_metadata(),
            "full_text": _report_service.get_ieee_paper_full_text()
        }

    @staticmethod
    def get_defense_checklist() -> Dict[str, Any]:
        return _report_service.get_defense_checklist()

    @staticmethod
    def get_video_demo_script() -> Dict[str, Any]:
        return _report_service.get_video_demo_script()

    @staticmethod
    def dispatch_request(
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Any]:
        """
        Universal edge REST router for HTTP handler and unit tests.
        """
        body = body or {}
        query = query or {}
        method = method.upper()

        def _get_q(name: str, default: Any = None) -> Any:
            val = query.get(name)
            if isinstance(val, list):
                return val[0] if len(val) > 0 else default
            return val if val is not None else default

        if method == "GET":
            if path == "/api/health":
                return 200, {
                    "status": "healthy",
                    "edge_device": "Raspberry Pi 5 (Quad Cortex-A76 @ 2.4GHz)",
                    "npu_accel": "Hailo-8L / Arm NEON XNNPACK",
                    "offline_mode": True,
                    "sqlite_connected": True
                }
            elif path == "/api/stats":
                return 200, InspectionService.get_stats()
            elif path == "/api/history":
                limit = int(_get_q("limit", 50))
                offset = int(_get_q("offset", 0))
                product_id = _get_q("product_id")
                defect_type = _get_q("defect_type")
                severity = _get_q("severity")
                decision = _get_q("decision")
                conf_min = float(_get_q("confidence_min")) if _get_q("confidence_min") is not None else None
                conf_max = float(_get_q("confidence_max")) if _get_q("confidence_max") is not None else None
                sort_by = _get_q("sort_by", "timestamp")
                order = _get_q("order", "DESC")
                return 200, InspectionService.get_history(
                    limit=limit,
                    offset=offset,
                    product_id=product_id,
                    defect_type=defect_type,
                    severity=severity,
                    decision=decision,
                    confidence_min=conf_min,
                    confidence_max=conf_max,
                    sort_by=sort_by,
                    order=order
                )
            elif path == "/api/reports/shift":
                shift_name = _get_q("shift", "Current Shift")
                start_date = _get_q("start_date")
                end_date = _get_q("end_date")
                return 200, InspectionService.get_shift_report(shift_name, start_date, end_date)
            elif path.startswith("/api/reports/certificate/"):
                inspection_id = path.split("/api/reports/certificate/")[1]
                cert = InspectionService.get_inspection_certificate(inspection_id)
                if not cert:
                    return 404, {"error": "Inspection record not found for certificate generation"}
                return 200, cert
            elif path == "/api/history/export":
                product_id = _get_q("product_id")
                defect_type = _get_q("defect_type")
                severity = _get_q("severity")
                decision = _get_q("decision")
                csv_str = InspectionService.export_csv(
                    product_id=product_id,
                    defect_type=defect_type,
                    severity=severity,
                    decision=decision
                )
                return 200, {"csv": csv_str, "format": "text/csv", "filename": "qualiedge_inspections.csv"}
            elif path == "/api/db/maintenance":
                return 200, InspectionService.get_db_maintenance()
            elif path.startswith("/api/inspection/"):
                inspection_id = path.split("/api/inspection/")[1]
                rec = InspectionService.get_inspection(inspection_id)
                if not rec:
                    return 404, {"error": "Inspection record not found"}
                return 200, rec
            elif path == "/api/camera/stream":
                return 200, {"status": "stream_ready", "format": "MJPEG"}
            elif path in ("/api/benchmark/telemetry", "/api/benchmark/live-telemetry"):
                return 200, InspectionService.get_benchmark_telemetry()
            elif path == "/api/benchmark/hardware-matrix":
                return 200, InspectionService.get_hardware_comparison_matrix()
            elif path == "/api/deployment/thermal":
                return 200, InspectionService.get_thermal_telemetry()
            elif path == "/api/deployment/hailo":
                return 200, InspectionService.get_hailo_status()
            elif path == "/api/deployment/cores":
                return 200, InspectionService.get_core_affinities()
            elif path == "/api/deployment/verification":
                return 200, InspectionService.get_deployment_verification()
            elif path == "/api/deployment/systemd":
                return 200, {"systemd_unit": InspectionService.get_systemd_service(), "filename": "qualiedge.service"}
            elif path == "/api/deployment/boot-config":
                return 200, {"boot_config": InspectionService.get_boot_config(), "filename": "config.txt"}
            elif path == "/api/reports/ieee-paper":
                return 200, InspectionService.get_ieee_paper()
            elif path == "/api/reports/defense-checklist":
                return 200, InspectionService.get_defense_checklist()
            elif path == "/api/reports/demo-script":
                return 200, InspectionService.get_video_demo_script()
            else:
                return 404, {"error": f"Endpoint not found: {path}"}

        elif method == "POST":
            if path == "/api/inspect":
                product_id = body.get("product_id")
                return 200, InspectionService.run_inspection(product_id=product_id)
            elif path == "/api/operator/override":
                inspection_id = body.get("inspection_id")
                if not inspection_id:
                    return 400, {"error": "Missing inspection_id"}
                operator_id = body.get("operator_id", "OPERATOR-DEFAULT")
                action = body.get("action", "VERIFIED")
                notes = body.get("notes", "")
                return 200, InspectionService.operator_override(inspection_id, operator_id, action, notes)
            elif path == "/api/deployment/governor":
                gov = body.get("governor", "performance")
                res = InspectionService.set_cpu_governor(gov)
                return (200 if res.get("status") == "success" else 400), res
            elif path == "/api/benchmark/run":
                num_frames = int(body.get("num_frames", 100))
                target_device = body.get("target_device", "rpi5_hailo")
                simulate_heavy_load = bool(body.get("simulate_heavy_load", False))
                return 200, InspectionService.run_benchmark(num_frames, target_device, simulate_heavy_load)
            elif path == "/api/benchmark/stress-test":
                num_iterations = int(body.get("num_iterations", 250))
                target_device = body.get("target_device", "rpi5_hailo")
                return 200, InspectionService.run_stress_test(num_iterations, target_device)
            elif path == "/api/db/vacuum":
                return 200, InspectionService.vacuum_db()
            elif path == "/api/db/purge":
                days = int(body.get("days_older_than", 30))
                return 200, InspectionService.purge_db(days_older_than=days)
            else:
                return 404, {"error": f"Endpoint not found: {path}"}

        return 405, {"error": f"Method {method} not allowed"}


# ==============================================================================
# FastAPI App Definition (Active when FastAPI is installed)
# ==============================================================================
if HAS_FASTAPI:
    app = FastAPI(
        title="QualiEdge Industrial Inspection API",
        version="1.0.0",
        description="Edge AI Industrial Defect Detection & Quality Control Assistant"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health():
        return {
            "status": "healthy",
            "edge_device": "Raspberry Pi 5 (Quad Cortex-A76 @ 2.4GHz)",
            "npu_accel": "Hailo-8L (Optional 13 TOPS PCIe M.2)",
            "offline_mode": True,
            "sqlite_connected": True
        }

    @app.get("/api/stats")
    def stats():
        return InspectionService.get_stats()

    @app.get("/api/history")
    def history(
        limit: int = 50,
        offset: int = 0,
        product_id: Optional[str] = None,
        defect_type: Optional[str] = None,
        severity: Optional[str] = None,
        decision: Optional[str] = None
    ):
        return InspectionService.get_history(limit, offset, product_id, defect_type, severity, decision)

    @app.get("/api/inspection/{inspection_id}")
    def get_single_inspection(inspection_id: str):
        rec = InspectionService.get_inspection(inspection_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Inspection record not found")
        return rec

    @app.post("/api/inspect")
    async def inspect_endpoint(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        product_id = body.get("product_id")
        return InspectionService.run_inspection(product_id=product_id)

    @app.post("/api/operator/override")
    async def operator_override_endpoint(request: Request):
        body = await request.json()
        inspection_id = body.get("inspection_id")
        operator_id = body.get("operator_id", "OPERATOR-DEFAULT")
        action = body.get("action", "VERIFIED")
        notes = body.get("notes", "")
        return InspectionService.operator_override(inspection_id, operator_id, action, notes)

    @app.get("/api/reports/shift")
    def shift_report_endpoint(
        shift: str = Query("Current Shift"),
        start_date: Optional[str] = Query(None),
        end_date: Optional[str] = Query(None)
    ):
        return InspectionService.get_shift_report(shift, start_date, end_date)

    @app.get("/api/reports/certificate/{inspection_id}")
    def certificate_endpoint(inspection_id: str):
        cert = InspectionService.get_inspection_certificate(inspection_id)
        if not cert:
            raise HTTPException(status_code=404, detail="Inspection record not found")
        return cert

    @app.get("/api/history/export")
    def export_endpoint(
        product_id: Optional[str] = Query(None),
        defect_type: Optional[str] = Query(None),
        severity: Optional[str] = Query(None),
        decision: Optional[str] = Query(None)
    ):
        csv_str = InspectionService.export_csv(product_id, defect_type, severity, decision)
        return {"csv": csv_str, "format": "text/csv", "filename": "qualiedge_inspections.csv"}

    @app.get("/api/db/maintenance")
    def db_maintenance_endpoint():
        return InspectionService.get_db_maintenance()

    @app.post("/api/db/vacuum")
    def db_vacuum_endpoint():
        return InspectionService.vacuum_db()

    @app.post("/api/db/purge")
    async def db_purge_endpoint(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        days = int(body.get("days_older_than", 30))
        return InspectionService.purge_db(days_older_than=days)

    @app.get("/api/benchmark/live-telemetry")
    @app.get("/api/benchmark/telemetry")
    def benchmark_telemetry_endpoint():
        return InspectionService.get_benchmark_telemetry()

    @app.get("/api/benchmark/hardware-matrix")
    def benchmark_hardware_matrix_endpoint():
        return InspectionService.get_hardware_comparison_matrix()

    @app.post("/api/benchmark/run")
    async def benchmark_run_endpoint(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        num_frames = int(body.get("num_frames", 100))
        target_device = body.get("target_device", "rpi5_hailo")
        simulate_heavy_load = bool(body.get("simulate_heavy_load", False))
        return InspectionService.run_benchmark(num_frames, target_device, simulate_heavy_load)

    @app.post("/api/benchmark/stress-test")
    async def benchmark_stress_endpoint(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        num_iterations = int(body.get("num_iterations", 250))
        target_device = body.get("target_device", "rpi5_hailo")
        return InspectionService.run_stress_test(num_iterations, target_device)

    @app.get("/api/deployment/thermal")
    def deployment_thermal_endpoint():
        return InspectionService.get_thermal_telemetry()

    @app.get("/api/deployment/hailo")
    def deployment_hailo_endpoint():
        return InspectionService.get_hailo_status()

    @app.get("/api/deployment/cores")
    def deployment_cores_endpoint():
        return InspectionService.get_core_affinities()

    @app.get("/api/deployment/verification")
    def deployment_verification_endpoint():
        return InspectionService.get_deployment_verification()

    @app.get("/api/deployment/systemd")
    def deployment_systemd_endpoint():
        return {"systemd_unit": InspectionService.get_systemd_service(), "filename": "qualiedge.service"}

    @app.get("/api/deployment/boot-config")
    def deployment_boot_config_endpoint():
        return {"boot_config": InspectionService.get_boot_config(), "filename": "config.txt"}

    @app.post("/api/deployment/governor")
    async def deployment_governor_endpoint(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        gov = body.get("governor", "performance")
        res = InspectionService.set_cpu_governor(gov)
        if res.get("status") != "success":
            raise HTTPException(status_code=400, detail=res.get("message"))
        return res

    @app.get("/api/reports/ieee-paper")
    def reports_ieee_endpoint():
        return InspectionService.get_ieee_paper()

    @app.get("/api/reports/defense-checklist")
    def reports_checklist_endpoint():
        return InspectionService.get_defense_checklist()

    @app.get("/api/reports/demo-script")
    def reports_demo_script_endpoint():
        return InspectionService.get_video_demo_script()
else:
    app = None


# ==============================================================================
# Built-In Lightweight Edge HTTP Server (Standard Library)
# ==============================================================================
class QualiEdgeHTTPHandler(BaseHTTPRequestHandler):
    """
    Standard library HTTP request handler providing identical REST endpoints
    without any third-party pip dependencies.
    """

    def _set_cors_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_cors_headers(200)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        status, data = InspectionService.dispatch_request("GET", path, query=query)
        self._set_cors_headers(status)
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = {}
        if content_length > 0:
            raw_body = self.rfile.read(content_length)
            try:
                body = json.loads(raw_body.decode("utf-8"))
            except Exception:
                body = {}
        status, data = InspectionService.dispatch_request("POST", path, body=body)
        self._set_cors_headers(status)
        self.wfile.write(json.dumps(data).encode("utf-8"))


def start_edge_server(port: int = 8000, host: str = "0.0.0.0"):
    """Starts the edge HTTP server."""
    server_address = (host, port)
    httpd = HTTPServer(server_address, QualiEdgeHTTPHandler)
    print(f"[SUCCESS] QualiEdge Edge REST API running on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
        print("[INFO] Server stopped.")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    start_edge_server(port=port)
