from __future__ import annotations
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import os

try:
    from backend.finalize.ontology import load_ontology, canonicalize_name_and_side
except Exception:  # script mode fallback
    from finalize.ontology import load_ontology, canonicalize_name_and_side  # type: ignore

# Simple global severity priority consistent with generator
SEVERITY_PRIORITY = {"minor": 1, "moderate": 2, "severe": 3}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _norm_severity(s: Optional[str]) -> str:
    t = _norm(s or "")
    if t in ("severe", "high"):  # accept synonyms
        return "severe"
    if t in ("moderate", "medium"):
        return "moderate"
    return "minor"


@dataclass
class Prov:
    # Track provenance of a merged part
    sources: List[int]
    decisions: List[str]


def _key_for(name: str, side: Optional[str], location: Optional[str]) -> Tuple[str, str]:
    # Prefer explicit side when available; fallback to normalized location bucket
    loc_key = _norm(side or location or "")
    return (_norm(name), loc_key)


def consolidate_parts(
    parts: List[dict],
    potential_parts: Optional[List[dict]] = None,
    ontology_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Deterministically consolidate parts using ontology and heuristics.

    - Canonicalizes names against ontology and extracts side.
    - Merges duplicates by (canonical_name, side/location) key.
    - Prefers highest severity, richer description, and retains verification evidence.
    - Produces provenance for auditability and identifies ambiguous clusters.
    """
    ontology = load_ontology(ontology_path)
    potential_parts = potential_parts or []

    clusters: Dict[Tuple[str, str], Dict[str, Any]] = {}
    provenance: Dict[Tuple[str, str], Prov] = {}
    ambiguous_clusters: List[Dict[str, Any]] = []

    def _ingest(part: dict, idx: int, reason: str) -> None:
        raw_name = part.get("name", "")
        raw_loc = part.get("location")
        canon_name, side = canonicalize_name_and_side(raw_name, raw_loc, ontology)
        key = _key_for(canon_name, side, raw_loc)
        item = dict(part)
        item["name"] = canon_name
        if side and not _norm(item.get("location")):
            item["location"] = side
        if item.get("severity") is not None:
            item["severity"] = _norm_severity(item.get("severity"))
        # Start/merge cluster
        if key not in clusters:
            clusters[key] = item
            provenance[key] = Prov(sources=[idx], decisions=[f"init:{reason}"])
        else:
            base = clusters[key]
            # severity: take max
            a = SEVERITY_PRIORITY.get(_norm_severity(base.get("severity")), 1)
            b = SEVERITY_PRIORITY.get(_norm_severity(item.get("severity")), 1)
            if b > a:
                base["severity"] = item.get("severity")
                provenance[key].decisions.append("severity_promoted")
            # description/notes: prefer longer
            for f in ("description", "notes"):
                cur = str(base.get(f, ""))
                new = str(item.get(f, ""))
                if len(new) > len(cur):
                    base[f] = new
            # copy fields if empty
            for f in ("damage_type", "repair_method", "category"):
                if (not base.get(f)) and item.get(f):
                    base[f] = item.get(f)
            # votes/verify: prefer larger votes and append verify passes
            try:
                if int(item.get("_votes", 0)) > int(base.get("_votes", 0)):
                    base["_votes"] = int(item.get("_votes", 0))
            except Exception:
                pass
            try:
                if item.get("_verify") and not base.get("_verify"):
                    base["_verify"] = item.get("_verify")
            except Exception:
                pass
            provenance[key].sources.append(idx)
            provenance[key].decisions.append("merged")

    # Ingest definitive parts
    for i, p in enumerate(parts):
        _ingest(p, i, "definitive")
    # Ingest potential parts as soft candidates (kept separate but merged for ambiguity evaluation)
    base_index = len(parts)
    for j, p in enumerate(potential_parts):
        _ingest(p, base_index + j, "potential")

    # Identify ambiguous clusters: conflicting evidence or severity swings
    for key, item in clusters.items():
        prov = provenance.get(key)
        if not prov:
            continue
        # Ambiguity if cluster has mixed sources and some are potential or low confidence verify
        multi_source = len(prov.sources) > 1
        low_conf = False
        try:
            ev = item.get("_verify") or {}
            passes = ev.get("passes", []) or []
            # consider low_conf if average conf < 0.6
            if passes:
                avg = sum(float(x.get("confidence", 0.0)) for x in passes) / max(1, len(passes))
                low_conf = avg < 0.6
        except Exception:
            low_conf = False
        if multi_source and low_conf:
            ambiguous_clusters.append({
                "key": {"name": key[0], "location": key[1]},
                "item": item,
                "provenance": {"sources": prov.sources, "decisions": prov.decisions},
            })

    finalized = list(clusters.values())

    # Potential parts: keep those that were not merged into a definitive cluster
    merged_keys = set(clusters.keys())
    pot_out: List[dict] = []
    for j, p in enumerate(potential_parts):
        canon_name, side = canonicalize_name_and_side(p.get("name", ""), p.get("location"), ontology)
        k = _key_for(canon_name, side, p.get("location"))
        if k not in merged_keys:
            q = dict(p)
            q["name"] = canon_name
            if side and not _norm(q.get("location")):
                q["location"] = side
            pot_out.append(q)

    # Deterministic sort
    def _sev(x: dict) -> int:
        return SEVERITY_PRIORITY.get(_norm_severity(x.get("severity")), 1)

    finalized.sort(key=lambda x: (-_sev(x), _norm(x.get("name")), _norm(x.get("location"))))
    pot_out.sort(key=lambda x: (-_sev(x), _norm(x.get("name")), _norm(x.get("location"))))

    prov_out = {
        f"{k[0]}|{k[1]}": {"sources": v.sources, "decisions": v.decisions}
        for k, v in provenance.items()
    }

    return {
        "damaged_parts": finalized,
        "potential_parts": pot_out,
        "provenance": prov_out,
        "ambiguous_clusters": ambiguous_clusters,
        "metrics": {
            "n_clusters": len(finalized),
            "n_ambiguous": len(ambiguous_clusters),
        },
    }
