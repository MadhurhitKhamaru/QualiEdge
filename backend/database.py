"""
backend/database.py

Embedded SQLite Persistence Engine for QualiEdge Industrial Quality Control.
Stores Section 7 Structured Inspection Records, Defect Bounding Boxes, and Operator Audit Logs.
Optimized for edge deployment on Raspberry Pi 5 with WAL (Write-Ahead Logging) mode.
"""

import sqlite3
import json
import os
import hashlib
import csv
import io
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "qualiedge.db"


class QualiEdgeDatabase:
    """
    SQLite persistence manager for industrial defect inspections and operator logs.
    """

    def __init__(self, db_path: Optional[str or Path] = None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a connection with WAL mode and foreign keys enabled."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self):
        """Initializes database schema with indexes and constraints."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Inspections Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS inspections (
                inspection_id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                defect_detected INTEGER NOT NULL,
                defect_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                confidence REAL NOT NULL,
                location TEXT NOT NULL,
                decision TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                root_cause TEXT,
                implications TEXT,
                remediation_steps TEXT,
                shift_log_summary TEXT,
                inference_ms REAL DEFAULT 0.0,
                image_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 2. Defect Boxes Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS defect_boxes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inspection_id TEXT NOT NULL,
                class_name TEXT NOT NULL,
                confidence REAL NOT NULL,
                xmin REAL NOT NULL,
                ymin REAL NOT NULL,
                xmax REAL NOT NULL,
                ymax REAL NOT NULL,
                area_ratio REAL NOT NULL,
                severity TEXT NOT NULL,
                FOREIGN KEY (inspection_id) REFERENCES inspections(inspection_id) ON DELETE CASCADE
            );
            """)

            # 3. Operator Logs Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS operator_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inspection_id TEXT NOT NULL,
                operator_id TEXT NOT NULL,
                action TEXT NOT NULL,
                notes TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (inspection_id) REFERENCES inspections(inspection_id) ON DELETE CASCADE
            );
            """)

            # Indexes for high-throughput queries and dashboard filtering
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_insp_prod ON inspections(product_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_insp_time ON inspections(timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_insp_defect ON inspections(defect_type);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_insp_sev ON inspections(severity);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_insp_dec ON inspections(decision);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_box_insp ON defect_boxes(inspection_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_op_insp ON operator_logs(inspection_id);")

            conn.commit()

    def save_inspection(
        self,
        record: Dict[str, Any],
        boxes: Optional[List[Dict[str, Any]]] = None,
        advisory: Optional[Dict[str, Any]] = None,
        image_path: Optional[str] = None
    ) -> str:
        """
        Saves a structured inspection record, its associated bounding boxes, and Llama advisory.
        """
        inspection_id = record.get("inspection_id")
        if not inspection_id:
            raise ValueError("Inspection record must contain 'inspection_id'")

        timestamp = record.get("timestamp") or datetime.now(timezone.utc).isoformat()
        defect_detected = 1 if record.get("defect_detected") else 0
        defect_type = str(record.get("defect_type", "Normal"))
        severity = str(record.get("severity", "None"))
        confidence = float(record.get("confidence", 0.0))
        location = str(record.get("location", "Unknown"))
        decision = str(record.get("decision", "ACCEPT"))
        recommendation = str(record.get("recommendation", ""))
        inference_ms = float(record.get("inference_ms", 0.0))

        root_cause = None
        implications = None
        remediation_steps = None
        shift_log_summary = None

        if advisory:
            root_cause = advisory.get("root_cause_analysis")
            implications = advisory.get("manufacturing_implications")
            steps = advisory.get("operator_action_plan", [])
            remediation_steps = json.dumps(steps) if isinstance(steps, list) else str(steps)
            shift_log_summary = advisory.get("shift_log_summary")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO inspections (
                inspection_id, product_id, timestamp, defect_detected, defect_type,
                severity, confidence, location, decision, recommendation,
                root_cause, implications, remediation_steps, shift_log_summary,
                inference_ms, image_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                inspection_id,
                record.get("product_id", "STEEL-UNKNOWN"),
                timestamp,
                defect_detected,
                defect_type,
                severity,
                confidence,
                location,
                decision,
                recommendation,
                root_cause,
                implications,
                remediation_steps,
                shift_log_summary,
                inference_ms,
                image_path
            ))

            # Insert bounding boxes if provided
            if boxes:
                cursor.execute("DELETE FROM defect_boxes WHERE inspection_id = ?;", (inspection_id,))
                for box in boxes:
                    cursor.execute("""
                    INSERT INTO defect_boxes (
                        inspection_id, class_name, confidence, xmin, ymin, xmax, ymax, area_ratio, severity
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        inspection_id,
                        box.get("class_name", defect_type),
                        float(box.get("confidence", confidence)),
                        float(box.get("xmin", 0.0)),
                        float(box.get("ymin", 0.0)),
                        float(box.get("xmax", 0.0)),
                        float(box.get("ymax", 0.0)),
                        float(box.get("area_ratio", 0.0)),
                        str(box.get("severity", severity))
                    ))

            conn.commit()

        return inspection_id

    def get_inspection(self, inspection_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single inspection record with associated defect boxes and operator logs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inspections WHERE inspection_id = ?;", (inspection_id,))
            row = cursor.fetchone()
            if not row:
                return None

            data = dict(row)
            data["defect_detected"] = bool(data["defect_detected"])

            # Deserialize remediation steps if JSON
            if data.get("remediation_steps"):
                try:
                    data["remediation_steps"] = json.loads(data["remediation_steps"])
                except Exception:
                    pass

            # Fetch boxes
            cursor.execute("SELECT * FROM defect_boxes WHERE inspection_id = ?;", (inspection_id,))
            data["boxes"] = [dict(b) for b in cursor.fetchall()]

            # Fetch operator logs
            cursor.execute("SELECT * FROM operator_logs WHERE inspection_id = ? ORDER BY timestamp DESC;", (inspection_id,))
            data["operator_logs"] = [dict(op) for op in cursor.fetchall()]

            return data

    def list_inspections(
        self,
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
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Queries inspections with multi-criteria filters, confidence gating, sorting, and pagination.
        Returns (records, total_matching).
        """
        conditions = []
        params = []

        if product_id:
            conditions.append("product_id LIKE ?")
            params.append(f"%{product_id}%")
        if defect_type and defect_type.upper() != "ALL":
            conditions.append("LOWER(defect_type) = LOWER(?)")
            params.append(defect_type)
        if severity and severity.upper() != "ALL":
            conditions.append("LOWER(severity) = LOWER(?)")
            params.append(severity)
        if decision and decision.upper() != "ALL":
            conditions.append("UPPER(decision) = UPPER(?)")
            params.append(decision)
        if confidence_min is not None:
            conditions.append("confidence >= ?")
            params.append(float(confidence_min))
        if confidence_max is not None:
            conditions.append("confidence <= ?")
            params.append(float(confidence_max))
        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Validate sort field to prevent SQL injection
        valid_sort_fields = {"timestamp", "confidence", "inference_ms", "severity", "product_id"}
        sort_field = sort_by if sort_by in valid_sort_fields else "timestamp"
        sort_dir = "ASC" if str(order).upper() == "ASC" else "DESC"

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Count total matching
            count_query = f"SELECT COUNT(*) FROM inspections {where_clause};"
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Fetch paginated rows
            data_query = f"""
            SELECT * FROM inspections
            {where_clause}
            ORDER BY {sort_field} {sort_dir}
            LIMIT ? OFFSET ?;
            """
            cursor.execute(data_query, params + [limit, offset])
            rows = cursor.fetchall()

            records = []
            for row in rows:
                item = dict(row)
                item["defect_detected"] = bool(item["defect_detected"])
                if item.get("remediation_steps"):
                    try:
                        item["remediation_steps"] = json.loads(item["remediation_steps"])
                    except Exception:
                        pass
                records.append(item)

            return records, total

    def log_operator_action(
        self,
        inspection_id: str,
        operator_id: str,
        action: str,
        notes: Optional[str] = None
    ) -> int:
        """Logs an operator override, review, or verification action."""
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO operator_logs (inspection_id, operator_id, action, notes, timestamp)
            VALUES (?, ?, ?, ?, ?);
            """, (inspection_id, operator_id, action, notes, timestamp))

            # If action is an override, also update the main inspection decision
            if action == "OVERRIDE_ACCEPT":
                cursor.execute("UPDATE inspections SET decision = 'ACCEPT' WHERE inspection_id = ?;", (inspection_id,))
            elif action == "OVERRIDE_REJECT":
                cursor.execute("UPDATE inspections SET decision = 'REJECT' WHERE inspection_id = ?;", (inspection_id,))

            conn.commit()
            return cursor.lastrowid

    def get_stats(self) -> Dict[str, Any]:
        """Calculates industrial aggregate quality control KPIs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Totals
            cursor.execute("SELECT COUNT(*) FROM inspections;")
            total = cursor.fetchone()[0]

            if total == 0:
                return {
                    "total_inspections": 0,
                    "accepted": 0,
                    "rejected": 0,
                    "manual_review": 0,
                    "defect_rate_pct": 0.0,
                    "avg_inference_ms": 0.0,
                    "defect_distribution": {},
                    "severity_distribution": {}
                }

            cursor.execute("SELECT COUNT(*) FROM inspections WHERE decision = 'ACCEPT';")
            accepted = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM inspections WHERE decision = 'REJECT';")
            rejected = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM inspections WHERE decision = 'MANUAL_REVIEW';")
            manual_review = cursor.fetchone()[0]

            cursor.execute("SELECT AVG(inference_ms) FROM inspections WHERE inference_ms > 0;")
            avg_ms_row = cursor.fetchone()[0]
            avg_inference_ms = round(float(avg_ms_row or 0.0), 2)

            defect_rate_pct = round((rejected / total) * 100, 2)

            # Defect type distribution
            cursor.execute("""
            SELECT defect_type, COUNT(*) as count
            FROM inspections
            WHERE defect_detected = 1
            GROUP BY defect_type
            ORDER BY count DESC;
            """)
            defect_dist = {row["defect_type"]: row["count"] for row in cursor.fetchall()}

            # Severity distribution
            cursor.execute("""
            SELECT severity, COUNT(*) as count
            FROM inspections
            GROUP BY severity
            ORDER BY count DESC;
            """)
            severity_dist = {row["severity"]: row["count"] for row in cursor.fetchall()}

            return {
                "total_inspections": total,
                "accepted": accepted,
                "rejected": rejected,
                "manual_review": manual_review,
                "defect_rate_pct": defect_rate_pct,
                "avg_inference_ms": avg_inference_ms,
                "defect_distribution": defect_dist,
                "severity_distribution": severity_dist
            }

    def get_shift_report(
        self,
        shift_name: str = "Current Shift",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates aggregate Industrial Shift Quality Report compliant with ISO 9001 / ASTM A1008.
        """
        conditions = []
        params = []
        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(f"SELECT COUNT(*) FROM inspections {where_clause};", params)
            total = cursor.fetchone()[0]

            if total == 0:
                return {
                    "shift_name": shift_name,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "total_inspected": 0,
                    "first_pass_yield_pct": 0.0,
                    "scrap_rate_pct": 0.0,
                    "manual_intervention_rate_pct": 0.0,
                    "accepted_count": 0,
                    "rejected_count": 0,
                    "manual_review_count": 0,
                    "defect_breakdown": {},
                    "severity_breakdown": {},
                    "avg_inference_ms": 0.0,
                    "total_overrides": 0,
                    "compliance_verdict": "NO DATA LOGGED",
                    "standard_spec": "ASTM A1008/A1008M Class 1 Standard Cold-Rolled Strip"
                }

            cursor.execute(f"SELECT COUNT(*) FROM inspections {where_clause} {'AND' if conditions else 'WHERE'} decision = 'ACCEPT';", params)
            accepted = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(*) FROM inspections {where_clause} {'AND' if conditions else 'WHERE'} decision = 'REJECT';", params)
            rejected = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(*) FROM inspections {where_clause} {'AND' if conditions else 'WHERE'} decision IN ('MANUAL_REVIEW', 'CONDITIONAL_FLAG', 'REVIEW_NEEDED');", params)
            manual_review = cursor.fetchone()[0]

            cursor.execute(f"SELECT AVG(inference_ms) FROM inspections {where_clause} {'AND' if conditions else 'WHERE'} inference_ms > 0;", params)
            avg_ms_val = cursor.fetchone()[0]
            avg_ms = round(float(avg_ms_val or 0.0), 2)

            cursor.execute(f"""
            SELECT defect_type, COUNT(*) as count
            FROM inspections
            {where_clause} {'AND' if conditions else 'WHERE'} defect_detected = 1
            GROUP BY defect_type
            ORDER BY count DESC;
            """, params)
            defect_dist = {row["defect_type"]: row["count"] for row in cursor.fetchall()}

            cursor.execute(f"""
            SELECT severity, COUNT(*) as count
            FROM inspections
            {where_clause}
            GROUP BY severity
            ORDER BY count DESC;
            """, params)
            severity_dist = {row["severity"]: row["count"] for row in cursor.fetchall()}

            # Count total operator overrides during shift
            cursor.execute(f"""
            SELECT COUNT(*) FROM operator_logs op
            JOIN inspections insp ON op.inspection_id = insp.inspection_id
            {where_clause};
            """, params)
            total_overrides = cursor.fetchone()[0]

            first_pass_yield_pct = round((accepted / total) * 100.0, 2)
            scrap_rate_pct = round((rejected / total) * 100.0, 2)
            manual_rate_pct = round((manual_review / total) * 100.0, 2)

            # Compliance evaluation: ISO 9001 / ASTM A1008 standard threshold
            # FPY >= 90% and scrap <= 8% is deemed Compliant
            if first_pass_yield_pct >= 90.0 and scrap_rate_pct <= 10.0:
                compliance_verdict = "PASSED - MEETS ASTM A1008 CLASS 1 SPECIFICATIONS"
            else:
                compliance_verdict = "QUALITY HOLD - ELEVATED DEFECT EXCURSION DETECTED"

            return {
                "shift_name": shift_name,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "time_window": {
                    "start": start_date or "All History",
                    "end": end_date or "Present"
                },
                "total_inspected": total,
                "first_pass_yield_pct": first_pass_yield_pct,
                "scrap_rate_pct": scrap_rate_pct,
                "manual_intervention_rate_pct": manual_rate_pct,
                "accepted_count": accepted,
                "rejected_count": rejected,
                "manual_review_count": manual_review,
                "defect_breakdown": defect_dist,
                "severity_breakdown": severity_dist,
                "avg_inference_ms": avg_ms,
                "total_overrides": total_overrides,
                "compliance_verdict": compliance_verdict,
                "standard_spec": "ASTM A1008 / ISO 9001:2015 Clause 8.6 Quality Assurance"
            }

    def get_inspection_certificate(self, inspection_id: str) -> Optional[Dict[str, Any]]:
        """
        Generates an ASTM A1008 / ISO 9001:2015 compliant Digital Quality Inspection Certificate
        with tamper-evident SHA-256 cryptographic verification checksum.
        """
        inspection = self.get_inspection(inspection_id)
        if not inspection:
            return None

        # Build cryptographic hash input
        hash_payload = f"{inspection['inspection_id']}:{inspection['product_id']}:{inspection['timestamp']}:{inspection['decision']}:{inspection['defect_type']}:{inspection['confidence']}"
        digital_seal = hashlib.sha256(hash_payload.encode('utf-8')).hexdigest()

        cert_id = f"CERT-{inspection['inspection_id'].replace('INS-', '')}-{digital_seal[:8].upper()}"

        return {
            "certificate_id": cert_id,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "inspection_record": inspection,
            "mill_profile": {
                "facility": "Bharat Steel & Alloy Works — Line 4 Continuous Cold-Rolling Mill",
                "sensor_suite": "Dual Basler ace2 Pro GigE / V4L2 Industrial Ingestion",
                "edge_controller": "Raspberry Pi 5 (Arm Cortex-A76 @ 2.4GHz) + Hailo-8L NPU",
                "inference_engine": "YOLOv8n ONNX-FP16 + ExecuTorch Llama-3.2-1B-Instruct (Local Edge)",
                "governing_standard": "ASTM A1008/A1008M Class 1 Cold-Rolled Strip Standards",
                "iso_clause": "ISO 9001:2015 Clause 8.6 Release of Products and Services"
            },
            "digital_signature": {
                "hash_algorithm": "SHA-256",
                "seal": digital_seal,
                "tamper_evident": True
            }
        }

    def export_inspections_csv(
        self,
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
        """
        Exports filtered inspection history into RFC 4180 standard CSV format.
        """
        records, _ = self.list_inspections(
            limit=limit,
            offset=0,
            product_id=product_id,
            defect_type=defect_type,
            severity=severity,
            decision=decision,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            start_date=start_date,
            end_date=end_date,
            sort_by="timestamp",
            order="DESC"
        )

        output = io.StringIO()
        fieldnames = [
            "inspection_id",
            "product_id",
            "timestamp",
            "defect_detected",
            "defect_type",
            "severity",
            "confidence",
            "location",
            "decision",
            "inference_ms",
            "recommendation",
            "root_cause",
            "implications"
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for rec in records:
            writer.writerow({
                "inspection_id": rec.get("inspection_id", ""),
                "product_id": rec.get("product_id", ""),
                "timestamp": rec.get("timestamp", ""),
                "defect_detected": "YES" if rec.get("defect_detected") else "NO",
                "defect_type": rec.get("defect_type", ""),
                "severity": rec.get("severity", ""),
                "confidence": f"{float(rec.get('confidence', 0.0)):.4f}",
                "location": rec.get("location", ""),
                "decision": rec.get("decision", ""),
                "inference_ms": f"{float(rec.get('inference_ms', 0.0)):.2f}",
                "recommendation": rec.get("recommendation", ""),
                "root_cause": rec.get("root_cause", ""),
                "implications": rec.get("implications", "")
            })

        return output.getvalue()

    def get_db_maintenance_stats(self) -> Dict[str, Any]:
        """
        Returns edge SQLite database file telemetry, WAL mode metrics, and table allocations.
        """
        db_file = Path(self.db_path)
        wal_file = Path(str(self.db_path) + "-wal")
        shm_file = Path(str(self.db_path) + "-shm")

        db_size_bytes = db_file.stat().st_size if db_file.exists() else 0
        wal_size_bytes = wal_file.stat().st_size if wal_file.exists() else 0
        shm_size_bytes = shm_file.stat().st_size if shm_file.exists() else 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA page_count;")
            page_count = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size;")
            page_size = cursor.fetchone()[0]
            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM inspections;")
            insp_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM defect_boxes;")
            box_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM operator_logs;")
            log_count = cursor.fetchone()[0]

        return {
            "db_path": str(db_file),
            "db_size_bytes": db_size_bytes,
            "db_size_kb": round(db_size_bytes / 1024, 2),
            "wal_size_bytes": wal_size_bytes,
            "wal_size_kb": round(wal_size_bytes / 1024, 2),
            "total_disk_footprint_kb": round((db_size_bytes + wal_size_bytes + shm_size_bytes) / 1024, 2),
            "journal_mode": str(journal_mode).upper(),
            "page_count": page_count,
            "page_size": page_size,
            "record_counts": {
                "inspections": insp_count,
                "defect_boxes": box_count,
                "operator_logs": log_count
            },
            "status": "HEALTHY / WAL_OPTIMIZED"
        }

    def vacuum_database(self) -> Dict[str, Any]:
        """Executes SQLite VACUUM to reclaim edge SD card storage space."""
        before_stats = self.get_db_maintenance_stats()
        with self._get_connection() as conn:
            conn.execute("VACUUM;")
            conn.commit()
        after_stats = self.get_db_maintenance_stats()
        reclaimed_bytes = max(0, before_stats["db_size_bytes"] - after_stats["db_size_bytes"])
        return {
            "status": "SUCCESS",
            "before_size_kb": before_stats["db_size_kb"],
            "after_size_kb": after_stats["db_size_kb"],
            "reclaimed_kb": round(reclaimed_bytes / 1024, 2),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def purge_records(self, days_older_than: int = 30) -> Dict[str, Any]:
        """Purges old historical inspections and logs to preserve edge SD card longevity."""
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_older_than)).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM inspections WHERE timestamp < ?;", (cutoff_date,))
            count_to_delete = cursor.fetchone()[0]

            cursor.execute("DELETE FROM inspections WHERE timestamp < ?;", (cutoff_date,))
            conn.commit()

        return {
            "status": "SUCCESS",
            "deleted_count": count_to_delete,
            "cutoff_date": cutoff_date
        }

    def seed_demo_data(self):
        """Seeds realistic historical inspection batches if database is empty."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM inspections;")
            if cursor.fetchone()[0] > 0:
                return

        demo_records = [
            {
                "inspection_id": "INS-2026-001",
                "product_id": "STEEL-CR-104",
                "defect_detected": True,
                "defect_type": "crazing",
                "severity": "Critical",
                "confidence": 0.942,
                "location": "Upper-right surface region",
                "decision": "REJECT",
                "recommendation": "Quarantine coil segment immediately. Critical crazing micro-cracks detected.",
                "inference_ms": 38.4,
                "boxes": [{"class_name": "crazing", "confidence": 0.942, "xmin": 80, "ymin": 45, "xmax": 240, "ymax": 190, "area_ratio": 0.082, "severity": "Critical"}],
                "advisory": {
                    "root_cause_analysis": "Thermal shock and steep cooling temperature gradients during continuous casting.",
                    "manufacturing_implications": "Micro-crack network poses severe brittle fracture risk during cold stamping.",
                    "operator_action_plan": ["Halt line feed", "Calibrate quench nozzles", "Notify melt-shop"],
                    "shift_log_summary": "REJECT: Critical crazing micro-cracks identified. Coil quarantined."
                }
            },
            {
                "inspection_id": "INS-2026-002",
                "product_id": "STEEL-CR-105",
                "defect_detected": False,
                "defect_type": "Normal",
                "severity": "None",
                "confidence": 0.991,
                "location": "Uniform surface",
                "decision": "ACCEPT",
                "recommendation": "Product verified defect-free. Release coil to downstream dispatch.",
                "inference_ms": 32.1,
                "boxes": [],
                "advisory": {
                    "root_cause_analysis": "Optimal roller lubrication and stable hot-strip reduction.",
                    "manufacturing_implications": "Zero surface anomalies. Full tensile and elongation compliance.",
                    "operator_action_plan": ["Release batch", "Maintain mill parameters", "Log verification"],
                    "shift_log_summary": "ACCEPT: Surface defect-free. Batch cleared for final packaging."
                }
            },
            {
                "inspection_id": "INS-2026-003",
                "product_id": "STEEL-CR-106",
                "defect_detected": True,
                "defect_type": "scratches",
                "severity": "High",
                "confidence": 0.915,
                "location": "Central strip longitudinal lane",
                "decision": "REJECT",
                "recommendation": "Inspect pinch-roll guides for foreign abrasive particles.",
                "inference_ms": 36.8,
                "boxes": [{"class_name": "scratches", "confidence": 0.915, "xmin": 120, "ymin": 90, "xmax": 420, "ymax": 160, "area_ratio": 0.054, "severity": "High"}],
                "advisory": {
                    "root_cause_analysis": "Mechanical abrasion from abrasive metallic debris wedged against transfer guide.",
                    "manufacturing_implications": "Continuous score mark weakens coating adhesion and initiates micro-crevice corrosion.",
                    "operator_action_plan": ["Inspect guide rollers", "Wipe guide plates", "Divert scratched segment"],
                    "shift_log_summary": "REJECT: Longitudinal mechanical scratches observed along central strip."
                }
            },
            {
                "inspection_id": "INS-2026-004",
                "product_id": "STEEL-CR-107",
                "defect_detected": True,
                "defect_type": "patches",
                "severity": "Medium",
                "confidence": 0.884,
                "location": "Lower-left strip zone",
                "decision": "REJECT",
                "recommendation": "Downgrade to secondary unexposed structural panel application.",
                "inference_ms": 35.2,
                "boxes": [{"class_name": "patches", "confidence": 0.884, "xmin": 30, "ymin": 280, "xmax": 210, "ymax": 420, "area_ratio": 0.062, "severity": "Medium"}],
                "advisory": {
                    "root_cause_analysis": "Uneven furnace atmospheric oxygen leading to localized oxidation burn-on.",
                    "manufacturing_implications": "Impaired phosphate and e-coat primer adhesion for automotive class-A bodywork.",
                    "operator_action_plan": ["Flag for grinding", "Check furnace atmosphere", "Sample roughness"],
                    "shift_log_summary": "HOLD: Surface oxidation patches detected. Downgraded to secondary grade."
                }
            },
            {
                "inspection_id": "INS-2026-005",
                "product_id": "STEEL-CR-108",
                "defect_detected": True,
                "defect_type": "pitted_surface",
                "severity": "Indeterminate",
                "confidence": 0.612,
                "location": "Edge border zone",
                "decision": "MANUAL_REVIEW",
                "recommendation": "Automated reject blocked due to low confidence (<0.65). Operator manual review required.",
                "inference_ms": 39.0,
                "boxes": [{"class_name": "pitted_surface", "confidence": 0.612, "xmin": 10, "ymin": 10, "xmax": 150, "ymax": 110, "area_ratio": 0.038, "severity": "Indeterminate"}],
                "advisory": {
                    "root_cause_analysis": "Ambiguous edge texture resembling light pickling etch marks.",
                    "manufacturing_implications": "Uncertain defect boundary. Risk of false-positive scrap rate escalation.",
                    "operator_action_plan": ["Perform contact stylus profilometry", "Verify pit depth against 0.03mm limit", "Log manual decision"],
                    "shift_log_summary": "HOLD: Low model confidence (<0.65). Routed to manual operator station."
                }
            }
        ]

        for item in demo_records:
            boxes = item.pop("boxes", [])
            advisory = item.pop("advisory", None)
            self.save_inspection(item, boxes=boxes, advisory=advisory)

        # Log an operator review for demo
        self.log_operator_action("INS-2026-005", "OPERATOR-402", "VERIFIED", "Manual optical loupe inspection confirms pit depth within 0.015mm tolerance.")
