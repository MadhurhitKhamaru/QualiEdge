"""
advisory_engine/prompt_templates.py

Industrial metallurgy prompt templates for Llama 3.2 Instruct via ExecuTorch.
Strictly adheres to:
1. Pure structured telemetry context (ZERO raw images / pixels).
2. Llama-3 special token format (<|begin_of_text|>, <|start_header_id|>, <|eot_id|>).
3. Concise, actionable industrial root-cause analysis and shift log summaries.
"""

from typing import Dict, Any

LLAMA3_SYSTEM_PROMPT = (
    "You are an on-device industrial metallurgist and quality assurance advisor "
    "operating locally on an edge steel cold-rolling line. "
    "Analyze the following structured inspection telemetry provided by the computer vision system. "
    "Diagnose the metallurgical root cause, assess fracture/safety risk, "
    "and provide 3 concise, actionable operator steps. "
    "Do NOT speculate beyond the provided telemetry facts."
)

def format_llama3_advisory_prompt(record_data: Dict[str, Any]) -> str:
    """
    Constructs a Llama-3 Instruct formatted prompt strictly from structured detection facts.
    """
    inspection_id = record_data.get("inspection_id", "INS-UNKNOWN")
    product_id = record_data.get("product_id", "STEEL-UNKNOWN")
    defect_detected = record_data.get("defect_detected", False)
    defect_type = record_data.get("defect_type", "Normal")
    severity = record_data.get("severity", "None")
    confidence = record_data.get("confidence", 0.0)
    location = record_data.get("location", "Unknown")
    decision = record_data.get("decision", "ACCEPT")

    user_content = (
        f"INSPECTION RECORD ID: {inspection_id}\n"
        f"PRODUCT / BATCH ID:   {product_id}\n"
        f"DEFECT STATUS:        {'DEFECT DETECTED' if defect_detected else 'DEFECT-FREE (NORMAL)'}\n"
        f"DEFECT CLASSIFICATION:{defect_type}\n"
        f"SEVERITY TIER:        {severity}\n"
        f"DETECTION CONFIDENCE: {confidence * 100:.1f}%\n"
        f"SURFACE LOCATION:     {location}\n"
        f"VISION DECISION:      {decision}\n\n"
        "Provide your quality assessment in 3 parts:\n"
        "1. Metallurgical Root Cause Analysis\n"
        "2. Manufacturing & Mechanical Implications\n"
        "3. Three Concrete Operator Remediation Steps"
    )

    formatted_prompt = (
        f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
        f"{LLAMA3_SYSTEM_PROMPT}<|eot_id|>\n"
        f"<|start_header_id|>user<|end_header_id|>\n\n"
        f"{user_content}<|eot_id|>\n"
        f"<|start_header_id|>assistant<|end_header_id|>\n\n"
    )

    return formatted_prompt

def format_shift_log_prompt(record_data: Dict[str, Any]) -> str:
    """
    Constructs prompt for generating a standardized ISO 9001 shift log summary entry.
    """
    user_content = (
        f"Generate a single-sentence formal shift log entry for Quality Audit:\n"
        f"Record: {record_data.get('inspection_id')} | Product: {record_data.get('product_id')} | "
        f"Status: {record_data.get('decision')} | Defect: {record_data.get('defect_type')} "
        f"({record_data.get('severity')}) at {record_data.get('location')}."
    )

    return (
        f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
        "You are an ISO 9001 logging assistant. Output only a one-line formal log summary.<|eot_id|>\n"
        f"<|start_header_id|>user<|end_header_id|>\n\n"
        f"{user_content}<|eot_id|>\n"
        f"<|start_header_id|>assistant<|end_header_id|>\n\n"
    )
