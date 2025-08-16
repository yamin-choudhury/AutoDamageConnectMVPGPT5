from __future__ import annotations
from typing import List, Dict, Any, Optional
import os

try:
    from backend.utils.json_parser import try_parse_json
    from backend.llm_clients.factory import create_vision_client
except Exception:
    from utils.json_parser import try_parse_json  # type: ignore
    from llm_clients.factory import create_vision_client  # type: ignore

# The judge is intentionally conservative: it cannot invent new parts.
# It only decides how to treat ambiguous clusters produced by merge.


def _client():
    return create_vision_client()


def judge_ambiguous(
    ambiguous_clusters: List[Dict[str, Any]],
    prompt_template: str,
    model: Optional[str] = None,
    temperature: float = 0.0,
) -> List[Dict[str, Any]]:
    """Ask LLM to judge ambiguous clusters.

    prompt_template should contain a placeholder <AMBIGUOUS_JSON>.
    Returns a list of decisions like:
    [{"key": {"name": str, "location": str}, "decision": "keep|drop|potential", "reason": str}]
    """
    if not ambiguous_clusters:
        return []
    prompt = prompt_template.replace("<AMBIGUOUS_JSON>", json_dumps_safe({"ambiguous_clusters": ambiguous_clusters}))
    resp = _client().text(prompt, temperature=temperature)
    parsed = try_parse_json(resp)
    if not isinstance(parsed, dict):
        return []
    decisions = parsed.get("decisions", []) or []
    out: List[Dict[str, Any]] = []
    for d in decisions:
        try:
            key = d.get("key") or {}
            name = str(key.get("name") or "").strip().lower()
            loc = str(key.get("location") or "").strip().lower()
            decision = str(d.get("decision") or "").strip().lower()
            if decision not in ("keep", "drop", "potential"):
                continue
            out.append({
                "key": {"name": name, "location": loc},
                "decision": decision,
                "reason": str(d.get("reason") or ""),
            })
        except Exception:
            continue
    return out


def json_dumps_safe(obj: Any) -> str:
    try:
        import json
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)
