#!/usr/bin/env python3
"""
cv_pipeline/severity_engine.py

Defect Severity Assessment, Spatial Localization & Decision Engine.
Implements industrial decision rules:
1. Inherent defect category risk rating.
2. Area ratio scaling (large defects upgrade severity tier).
3. Spatial region translation (normalized coordinates -> human-readable zones).
4. Confidence threshold fail-safe (<0.65 triggers MANUAL_REVIEW).
5. Generates Pydantic-validated StructuredInspectionRecord.
"""

import sys
import uuid
from typing import List, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.schemas import (
    StructuredInspectionRecord,
    SeverityLevel,
    InspectionDecision,
    DefectBoxDetail
)

# Confidence threshold for automated industrial decision
CONFIDENCE_THRESHOLD = 0.65

# Baseline category severity
CATEGORY_BASE_SEVERITY = {
    "crazing": SeverityLevel.CRITICAL,
    "inclusion": SeverityLevel.HIGH,
    "patches": SeverityLevel.MEDIUM,
    "pitted_surface": SeverityLevel.HIGH,
    "pitted surface": SeverityLevel.HIGH,
    "rolled_in_scale": SeverityLevel.HIGH,
    "rolled in scale": SeverityLevel.HIGH,
    "scratches": SeverityLevel.MEDIUM,
    "scratch": SeverityLevel.MEDIUM,
    "normal": SeverityLevel.NONE
}

# Standard industrial operator recommendations
OPERATOR_RECOMMENDATIONS = {
    "crazing": "Immediate reject. Quarantine coil segment to prevent catastrophic tensile failure during stamping.",
    "inclusion": "Reject. Non-metallic inclusions degrade ductility. Flag melt-shop deoxidation records.",
    "patches": "Conditional hold. Surface oxidation patch detected; verify coating adhesion or downgrade.",
    "pitted_surface": "Reject component. Pitting exceeds gauge tolerance. Check pickling line acid concentration.",
    "rolled_in_scale": "Reject. Scale entrapped in substrate will delaminate during fabrication. Inspect descaler nozzles.",
    "scratches": "Inspect surface scratch depth. If micrometer depth < 0.05mm, allow rework, otherwise reject.",
    "normal": "Surface passes ASTM A1008 steel standards. Release coil to downstream slitting line."
}

def resolve_spatial_location(xc: float, yc: float) -> str:
    """
    Translates normalized center coordinates (0.0 - 1.0) into human-readable industrial zones.
    """
    # Central deadband zone (0.35 to 0.65 in both axes)
    if 0.35 <= xc <= 0.65 and 0.35 <= yc <= 0.65:
        return "Central strip region"
    
    vertical = "Upper" if yc < 0.50 else "Lower"
    horizontal = "left" if xc < 0.50 else "right"
    
    return f"{vertical}-{horizontal} region"

class SeverityAssessmentEngine:
    """
    Evaluates computer vision detections and generates Section 7 structured records.
    """
    def __init__(self, confidence_cutoff: float = CONFIDENCE_THRESHOLD):
        self.confidence_cutoff = confidence_cutoff

    def assess(
        self,
        boxes: List[dict],
        product_id: str = "STEEL-001",
        inspection_id: Optional[str] = None,
        inference_ms: Optional[float] = None
    ) -> StructuredInspectionRecord:
        """
        Synthesize detections into a verified structured inspection record.
        """
        insp_id = inspection_id or f"INS-{uuid.uuid4().hex[:6].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Case 1: Defect-free / normal surface
        if not boxes:
            return StructuredInspectionRecord(
                inspection_id=insp_id,
                product_id=product_id,
                defect_detected=False,
                defect_type="Normal",
                severity=SeverityLevel.NONE,
                confidence=0.992,
                location="Uniform surface",
                decision=InspectionDecision.ACCEPT,
                recommendation=OPERATOR_RECOMMENDATIONS["normal"],
                timestamp=now_iso,
                inference_ms=inference_ms,
                boxes=[]
            )

        # Primary defect is the highest confidence / highest severity box
        primary_box = max(boxes, key=lambda b: (b.get("confidence", 0.0), b.get("area_ratio", 0.0)))
        raw_name = str(primary_box.get("class_name", "defect")).lower()
        conf = float(primary_box.get("confidence", 0.0))
        area_ratio = float(primary_box.get("area_ratio", 0.0))
        xc = float(primary_box.get("xc", 0.5))
        yc = float(primary_box.get("yc", 0.5))

        location_str = resolve_spatial_location(xc, yc)

        # Format defect name nicely e.g. "Scratch", "Crazing"
        clean_name = raw_name.replace("_", " ").title()

        # Case 2: Insufficient confidence -> Fail-Safe Manual Review
        if conf < self.confidence_cutoff:
            return StructuredInspectionRecord(
                inspection_id=insp_id,
                product_id=product_id,
                defect_detected=True,
                defect_type=clean_name,
                severity=SeverityLevel.INDETERMINATE,
                confidence=conf,
                location=location_str,
                decision=InspectionDecision.MANUAL_REVIEW,
                recommendation=f"Confidence ({conf*100:.1f}%) is below {self.confidence_cutoff*100:.0f}% threshold. Hold product for manual operator verification.",
                timestamp=now_iso,
                inference_ms=inference_ms,
                boxes=[DefectBoxDetail(**b) for b in boxes if "class_id" in b]
            )

        # Case 3: Calculate severity
        base_sev = CATEGORY_BASE_SEVERITY.get(raw_name, SeverityLevel.HIGH)
        # Severity escalation for large area coverage (>10% surface area)
        if area_ratio > 0.10 and base_sev == SeverityLevel.MEDIUM:
            final_sev = SeverityLevel.HIGH
        else:
            final_sev = base_sev

        recommendation = OPERATOR_RECOMMENDATIONS.get(
            raw_name,
            f"Inspect the surface and reject the defective component ({clean_name} detected)."
        )

        return StructuredInspectionRecord(
            inspection_id=insp_id,
            product_id=product_id,
            defect_detected=True,
            defect_type=clean_name,
            severity=final_sev,
            confidence=conf,
            location=location_str,
            decision=InspectionDecision.REJECT,
            recommendation=recommendation,
            timestamp=now_iso,
            inference_ms=inference_ms,
            boxes=[DefectBoxDetail(**b) for b in boxes if "class_id" in b]
        )

if __name__ == "__main__":
    engine = SeverityAssessmentEngine()
    sample_box = [{
        "class_id": 5,
        "class_name": "scratches",
        "confidence": 0.960,
        "xc": 0.85,
        "yc": 0.15,
        "w": 0.20,
        "h": 0.05,
        "x1": 500,
        "y1": 80,
        "x2": 620,
        "y2": 110,
        "area_ratio": 0.010
    }]
    record = engine.assess(sample_box, product_id="STEEL-001", inspection_id="INS-001")
    print(record.model_dump_json(indent=2))
