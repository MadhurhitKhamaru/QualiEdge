"""
backend/schemas.py

Pydantic schemas and data validation models for Industrial Quality Inspection.
Strictly conforms to Section 7 of the Master Project Specification.
"""

from enum import Enum
from typing import Optional, List
from datetime import datetime, timezone
try:
    from pydantic import BaseModel, Field, field_validator
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self):
            import json
            def convert(val):
                if hasattr(val, "value"):
                    return val.value
                if hasattr(val, "model_dump"):
                    return val.model_dump()
                if isinstance(val, list):
                    return [convert(item) for item in val]
                return val
            return {k: convert(v) for k, v in self.__dict__.items()}
        def model_dump_json(self, indent=None):
            import json
            return json.dumps(self.model_dump(), indent=indent)

    def Field(default=None, default_factory=None, **kwargs):
        if default_factory is not None:
            return default_factory()
        return default

    def field_validator(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

class SeverityLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"
    NONE = "None"
    INDETERMINATE = "Indeterminate"

class InspectionDecision(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    MANUAL_REVIEW = "MANUAL_REVIEW"

class DefectBoxDetail(BaseModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class StructuredInspectionRecord(BaseModel):
    """
    Mandatory Section 7 Inspection Payload.
    Used for SQLite persistence, REST endpoints, and Local Llama ExecuTorch context.
    """
    def __init__(
        self,
        inspection_id: str,
        product_id: str,
        defect_detected: bool,
        defect_type: str,
        severity: SeverityLevel,
        confidence: float,
        location: str,
        decision: InspectionDecision,
        recommendation: str,
        timestamp: Optional[str] = None,
        inference_ms: Optional[float] = None,
        boxes: Optional[List[DefectBoxDetail]] = None
    ):
        self.inspection_id = inspection_id
        self.product_id = product_id
        self.defect_detected = defect_detected
        self.defect_type = defect_type
        self.severity = severity
        self.confidence = round(float(confidence), 4)
        self.location = location
        self.decision = decision
        self.recommendation = recommendation
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.inference_ms = inference_ms
        self.boxes = boxes or []
