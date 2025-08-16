from __future__ import annotations
from typing import Dict, Any, Optional

try:
    from backend.utils.json_parser import try_parse_json
    from backend.llm_clients.factory import create_vision_client
except Exception:
    from utils.json_parser import try_parse_json  # type: ignore
    from llm_clients.factory import create_vision_client  # type: ignore


def _client():
    return create_vision_client()


def compose_narrative(
    report_json: Dict[str, Any],
    prompt_template: str,
    temperature: float = 0.1,
) -> Dict[str, Any]:
    """Compose enterprise-grade narrative sections from final structured report.

    prompt_template should contain a placeholder <FINAL_REPORT_JSON>.
    Returns a dict with keys like: executive_summary, safety_highlights, repair_plan_overview
    """
    import json

    prompt = prompt_template.replace("<FINAL_REPORT_JSON>", json.dumps(report_json, ensure_ascii=False))
    resp = _client().text(prompt, temperature=temperature)
    parsed = try_parse_json(resp) or {}
    if not isinstance(parsed, dict):
        return {
            "executive_summary": "",
            "safety_highlights": [],
            "repair_plan_overview": "",
        }
    # Normalize expected fields
    out = {
        "executive_summary": str(parsed.get("executive_summary", "")),
        "safety_highlights": list(parsed.get("safety_highlights", []) or []),
        "repair_plan_overview": str(parsed.get("repair_plan_overview", parsed.get("repair_overview", ""))),
    }
    return out
