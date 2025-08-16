from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
import re

NormMap = Dict[str, str]

_default_ontology = {
    "labels": [
        "front bumper", "rear bumper", "hood", "trunk lid", "grille",
        "left fender", "right fender", "left door", "right door",
        "left mirror", "right mirror", "windshield", "rear window",
        "left headlight", "right headlight", "left taillight", "right taillight",
        "roof", "left quarter panel", "right quarter panel"
    ],
    "synonyms": {
        "bonnet": "hood",
        "boot": "trunk lid",
        "trunk": "trunk lid",
        "tail light": "taillight",
        "head light": "headlight",
        "rear bumper": "rear bumper",
        "front bumper": "front bumper",
        "windscreen": "windshield",
        "left wing": "left fender",
        "right wing": "right fender",
        "lhs fender": "left fender",
        "rhs fender": "right fender",
        "lhs door": "left door",
        "rhs door": "right door",
    }
}

_side_words = ["left", "right", "front", "rear", "back"]


def load_ontology(path: Optional[str]) -> dict:
    if not path:
        return _default_ontology
    p = Path(path)
    try:
        if p.exists():
            return json.loads(p.read_text())
    except Exception:
        pass
    return _default_ontology


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def extract_side(name: str, location: Optional[str] = None) -> Tuple[Optional[str], str]:
    s = _norm(" ".join([name or "", location or ""]))
    side: Optional[str] = None
    if "left" in s:
        side = "left"
    elif "right" in s:
        side = "right"
    # front/back often part of canonical label already, keep as part of name
    return side, s


def canonicalize_label(raw_name: str, ontology: dict) -> str:
    name_n = _norm(raw_name)
    syn = ontology.get("synonyms", {})
    if name_n in syn:
        return syn[name_n]
    # strip side words
    base = name_n
    for w in _side_words:
        base = base.replace(w, "").strip()
    base = re.sub(r"\s+", " ", base)
    # direct label match
    labels = [ _norm(l) for l in ontology.get("labels", []) ]
    # choose best by simple token overlap
    def score(label: str) -> float:
        t1 = set(base.split())
        t2 = set(label.split())
        if not t1 or not t2:
            return 0.0
        return len(t1 & t2) / len(t1 | t2)
    best = None
    best_sc = 0.0
    for lab in labels:
        sc = score(lab)
        if sc > best_sc:
            best_sc = sc
            best = lab
    return best if best else base


def canonicalize_name_and_side(name: str, location: Optional[str], ontology: dict) -> Tuple[str, Optional[str]]:
    side, _ = extract_side(name, location)
    canon = canonicalize_label(name, ontology)
    # add explicit side to name if not inherently front/back
    if side and not canon.startswith(side):
        # e.g., "left door" vs "door" -> return canonical "door" and side separately
        return canon, side
    return canon, side
