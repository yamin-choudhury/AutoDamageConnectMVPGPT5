from __future__ import annotations
import json
import os
import re
from typing import Any, Optional, Type, TypeVar

try:
    # Prefer local import when running as package
    from backend.schema import DetectionLLMOutput, VerifyLLMOutput
except Exception:
    # Fallback when running from within backend/ as script
    from schema import DetectionLLMOutput, VerifyLLMOutput  # type: ignore

T = TypeVar("T")

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_BOOL_NONE_FIXES = [
    (re.compile(r"(?<![\w\-\'])\bTrue\b"), "true"),
    (re.compile(r"(?<![\w\-\'])\bFalse\b"), "false"),
    (re.compile(r"(?<![\w\-\'])\bNone\b"), "null"),
]

_TRAILING_COMMA_RE = re.compile(r",\s*(\]|\})")

# Maximum repair attempts can be tuned via env
MAX_REPAIR_PASSES = max(0, int(os.getenv("JSON_REPAIR_PASSES", "2")))


def extract_json_text(text: str) -> str:
    """Strip Markdown code fences if present and trim whitespace."""
    if not text:
        return ""
    s = text.strip()
    # Remove surrounding code fences
    s = _CODE_FENCE_RE.sub("", s).strip()
    return s


def _braces_slice(s: str) -> Optional[str]:
    l = s.find("{")
    r = s.rfind("}")
    if l != -1 and r != -1 and r > l:
        return s[l : r + 1]
    return None


def _apply_simple_repairs(s: str) -> str:
    out = s
    # Replace Python-style booleans/None
    for pat, repl in _BOOL_NONE_FIXES:
        out = pat.sub(repl, out)
    # Remove trailing commas before ] or }
    out = _TRAILING_COMMA_RE.sub(r"\1", out)
    return out


def try_parse_json(text: str) -> Optional[Any]:
    """Attempt to parse possibly-imperfect JSON with incremental repairs.

    Returns parsed object or None if it cannot be parsed.
    """
    if not text:
        return None
    s = extract_json_text(text)

    # First attempt: direct
    try:
        return json.loads(s)
    except Exception:
        pass

    # Second attempt: slice to outermost braces
    sliced = _braces_slice(s)
    if sliced:
        try:
            return json.loads(sliced)
        except Exception:
            s = sliced

    # Incremental repairs
    cur = s
    for _ in range(MAX_REPAIR_PASSES):
        repaired = _apply_simple_repairs(cur)
        if repaired == cur:
            break
        try:
            return json.loads(repaired)
        except Exception:
            cur = repaired

    return None


def validate_detection_output(data: Any) -> dict:
    """Validate/coerce raw data to DetectionLLMOutput -> dict."""
    model = DetectionLLMOutput.parse_obj(data)
    return model.dict()


def validate_verify_output(data: Any) -> dict:
    """Validate/coerce raw data to VerifyLLMOutput -> dict."""
    model = VerifyLLMOutput.parse_obj(data)
    return model.dict()
