#!/usr/bin/env python3
"""Two-phase damage report generator: Detection → Enrichment.

Usage:
 python generate_damage_report_staged.py --images_dir copartimages/vehicle1 \
                                        --out report_full.json
"""
from __future__ import annotations
import argparse, base64, json, os, sys, requests
import asyncio, concurrent.futures, threading
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin
from typing import Optional
from typing import List
from io import BytesIO

import openai
from dotenv import load_dotenv
from PIL import Image, ImageOps, ImageFilter, ImageStat
import time, random
import hashlib
from tqdm import tqdm
from copy import deepcopy


# Look for prompt files one directory up (repo root) to ensure they are present inside the container
# Try ./prompts beside this file first, else ../prompts (repo root)
_prompts_same = Path(__file__).resolve().parent / "prompts"
PROMPTS_DIR = _prompts_same if _prompts_same.exists() else Path(__file__).resolve().parent.parent / "prompts"
PHASE0_QUICK_PROMPT   = PROMPTS_DIR / "detect_quick_prompt.txt"
PHASE1_FRONT_ENTERPRISE_PROMPT = PROMPTS_DIR / "detect_front_enterprise.txt"
PHASE1_SIDE_ENTERPRISE_PROMPT  = PROMPTS_DIR / "detect_side_enterprise.txt"
PHASE1_REAR_ENTERPRISE_PROMPT  = PROMPTS_DIR / "detect_rear_enterprise.txt"
GENERIC_AREAS_PROMPT = PROMPTS_DIR / "detect_generic_areas.txt"
VEHICLE_ID_PROMPT = PROMPTS_DIR / "identify_vehicle.txt"
PHASE2_PROMPT = PROMPTS_DIR / "describe_parts_prompt.txt"
PHASE3_PROMPT = PROMPTS_DIR / "plan_parts_prompt.txt"
PHASE4_PROMPT = PROMPTS_DIR / "summary_prompt.txt"
PHASE1_ENTERPRISE_PROMPT = PROMPTS_DIR / "detect_enterprise_prompt.txt"
PHASE1_COMPLETENESS_PROMPT = PROMPTS_DIR / "detect_missing_parts.txt"
PHASE5_VERIFY_PROMPT = PROMPTS_DIR / "verify_part_prompt.txt"


# ----------------------- OpenAI client tuning -------------------------
# Global retry/backoff and concurrency limits to reduce failures and load
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "5"))
OPENAI_BACKOFF_BASE = float(os.getenv("OPENAI_BACKOFF_BASE", "0.5"))  # seconds
OPENAI_CONCURRENCY = int(os.getenv("OPENAI_CONCURRENCY", "4"))
_openai_sem = threading.Semaphore(OPENAI_CONCURRENCY)
MAX_DAMAGED_PARTS = int(os.getenv("MAX_DAMAGED_PARTS", "5"))  # 0 = no cap
PHASE2_ALLOW_NEW_PARTS = os.getenv("PHASE2_ALLOW_NEW_PARTS", "0") == "1"  # default OFF to reduce hallucinations
PERSIST_MAX_UNION = os.getenv("PERSIST_MAX_UNION", "1") == "1"
CACHE_SUPERSET_DIR = (Path(__file__).resolve().parent / "cache" / "supersets")
PERSIST_MIN_SUPPORT = int(os.getenv("PERSIST_MIN_SUPPORT", "1"))
ENABLE_COMPLETENESS_PASS = os.getenv("ENABLE_COMPLETENESS_PASS", "1") == "1"
STRICT_MODE = os.getenv("STRICT_MODE", "1") == "1"
# Comprehensive mode prioritises recall and produces a dual-track output
# with definitive damaged_parts and potential_parts.
COMPREHENSIVE_MODE = os.getenv("COMPREHENSIVE_MODE", "0") == "1"
MIN_VOTES_PER_PART = int(os.getenv("MIN_VOTES_PER_PART", "2"))  # Default stricter consensus
MIN_VOTES_SEVERE = int(os.getenv("MIN_VOTES_SEVERE", str(MIN_VOTES_PER_PART)))
MIN_VOTES_MODERATE = int(os.getenv("MIN_VOTES_MODERATE", str(MIN_VOTES_PER_PART)))
MIN_VOTES_MINOR = int(os.getenv("MIN_VOTES_MINOR", str(max(MIN_VOTES_PER_PART, 3))))
ENABLE_VERIFICATION_PASS = os.getenv("ENABLE_VERIFICATION_PASS", "1") == "1"
VERIFY_MIN_CONFIDENCE = float(os.getenv("VERIFY_MIN_CONFIDENCE", "0.65" if STRICT_MODE else "0.55"))
DETECT_MIN_CONFIDENCE = float(os.getenv("DETECT_MIN_CONFIDENCE", "0.0"))
DETECTION_TEMPS = [0.0] if STRICT_MODE else [0.0, 0.2]
# IoU threshold for clustering parts across runs (prevents vote inflation)
CLUSTER_IOU_THRESH = float(os.getenv("CLUSTER_IOU_THRESH", "0.4"))
# Severity-aware verification confidence thresholds (fallback to VERIFY_MIN_CONFIDENCE)
VERIFY_CONF_SEVERE = float(os.getenv("VERIFY_CONF_SEVERE", str(VERIFY_MIN_CONFIDENCE)))
VERIFY_CONF_MODERATE = float(os.getenv("VERIFY_CONF_MODERATE", str(VERIFY_MIN_CONFIDENCE)))
VERIFY_CONF_MINOR = float(os.getenv("VERIFY_CONF_MINOR", str(VERIFY_MIN_CONFIDENCE)))
# Verification temperatures (comma-separated env like '0.0,0.2')
_vtemps = os.getenv("VERIFY_TEMPS")
if _vtemps:
    try:
        VERIFY_TEMPS = [float(x.strip()) for x in _vtemps.split(",") if x.strip()]
    except Exception:
        VERIFY_TEMPS = [0.0, 0.2]
else:
    VERIFY_TEMPS = [0.0, 0.2]
# Consensus requirements per severity (number of verification passes that must agree)
VERIFY_REQUIRE_PASSES_SEVERE = int(os.getenv("VERIFY_REQUIRE_PASSES_SEVERE", "2"))
VERIFY_REQUIRE_PASSES_MODERATE = int(os.getenv("VERIFY_REQUIRE_PASSES_MODERATE", "2"))
VERIFY_REQUIRE_PASSES_MINOR = int(os.getenv("VERIFY_REQUIRE_PASSES_MINOR", "1"))

def get_candidate_boxes(img_path: Path):
    """Return empty list – YOLO fully removed."""
    return []

# ----------------------------------------------------------------------

def encode_image_b64(p: Path, max_px: int = 1600, quality: int = 80) -> str:
    """Return a data URL for a RESIZED JPEG of the image.
    This avoids embedding original large files in prompts.
    """
    img = Image.open(p).convert("RGB")
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px))
    buf = BytesIO()
    # Use reasonable quality to retain detail while keeping size small
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    buf.seek(0)
    return "data:image/jpeg;base64," + base64.b64encode(buf.read()).decode()


def call_openai_vision(
    prompt: str,
    images: List[Path],
    model: str = "gpt-4o",
    temperature: float = 0.2,
    max_images: Optional[int] = None,
) -> str:
    """Call OpenAI Vision with a bounded set of downsized images.
    If max_images is set, sample a small subset of images to keep payload reasonable.
    """
    # Select quality-diverse subset when capped
    if max_images is not None and len(images) > max_images:
        deduped = dedupe_by_phash(images)
        use_images = select_diverse_top(deduped, k=max_images)
    else:
        use_images = images

    user_parts = [{"type": "text", "text": "Please analyse all images and reply with JSON only."}]
    for img in use_images:
        user_parts.append({"type": "image_url", "image_url": {"url": encode_image_b64(img)}})

    # Concurrency-limit and retry with backoff
    with _openai_sem:
        last_err = None
        for attempt in range(OPENAI_MAX_RETRIES):
            try:
                resp = openai.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_parts}],
                    max_tokens=6144,
                    temperature=temperature,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                last_err = e
                if attempt < OPENAI_MAX_RETRIES - 1:
                    sleep_s = OPENAI_BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 0.25)
                    time.sleep(sleep_s)
                else:
                    raise last_err


def call_openai_text(prompt: str, model: str = "gpt-4o", temperature: float = 0.2) -> str:
    with _openai_sem:
        last_err = None
        for attempt in range(OPENAI_MAX_RETRIES):
            try:
                resp = openai.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": prompt}],
                    max_tokens=6144,
                    temperature=temperature,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                last_err = e
                if attempt < OPENAI_MAX_RETRIES - 1:
                    sleep_s = OPENAI_BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 0.25)
                    time.sleep(sleep_s)
                else:
                    raise last_err


# ----------------------- Image cropping utilities --------------------
# ----------------------- Image quality & selection --------------------
def _downsample_for_stats(img: Image.Image, size: int = 128) -> Image.Image:
    """Small helper to make stats fast and stable."""
    if max(img.size) > size:
        img = img.copy()
        img.thumbnail((size, size))
    return img


def score_image(p: Path) -> float:
    """Compute a lightweight quality score [0..1] using PIL only.
    Factors: sharpness (edges), exposure (avoid too dark/bright), glare (near-white ratio).
    """
    try:
        img = Image.open(p).convert("RGB")
        img_small = _downsample_for_stats(img)
        gray = img_small.convert("L")
        # Sharpness proxy: mean edge magnitude
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_mean = ImageStat.Stat(edges).mean[0] / 255.0  # 0..1
        # Exposure: penalize extremes via clipped pixel ratio
        pixels = list(gray.getdata())
        n = len(pixels)
        if n == 0:
            return 0.0
        clipped_low = sum(1 for v in pixels if v <= 8) / n
        clipped_high = sum(1 for v in pixels if v >= 247) / n
        glare = clipped_high  # treat as glare
        # Exposure midness: prefer mean around 110..150 range
        mean_l = ImageStat.Stat(gray).mean[0]
        mid_dev = abs(mean_l - 128) / 128.0  # 0 good .. ~1 bad
        exposure_score = max(0.0, 1.0 - mid_dev)
        # Combine
        score = 0.6 * edge_mean + 0.3 * exposure_score + 0.1 * max(0.0, 1.0 - glare * 5)
        return float(max(0.0, min(1.0, score)))
    except Exception:
        return 0.0


def ahash(p: Path, hash_size: int = 8) -> int:
    """Average hash (aHash) 8x8 -> 64-bit integer."""
    try:
        img = Image.open(p).convert("L")
        img = img.resize((hash_size, hash_size), Image.BILINEAR)
        pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)
        bits = 0
        for i, v in enumerate(pixels):
            bits |= (1 if v >= avg else 0) << i
        return bits
    except Exception:
        return 0


def hamming_distance(a: int, b: int) -> int:
    x = a ^ b
    # Count bits
    cnt = 0
    while x:
        x &= x - 1
        cnt += 1
    return cnt


# ----------------------- Persistent superset helpers --------------------
SEVERITY_PRIORITY_GLOBAL = {"severe": 3, "moderate": 2, "minor": 1}

def _norm(s: str) -> str:
    return (s or "").strip().lower()

def _key_for_part(p: dict) -> tuple[str, str]:
    # Identity is based on (name, location). Category is advisory and should not split identical parts.
    return (_norm(p.get("name", "")), _norm(p.get("location", "")))

# ----------------------- Canonicalization helpers ---------------------
def _canon_severity(s: str) -> str:
    s = _norm(s)
    mapping = {
        "low": "minor", "minor": "minor", "slight": "minor", "light": "minor",
        "medium": "moderate", "moderate": "moderate",
        "high": "severe", "severe": "severe", "major": "severe", "extreme": "severe",
    }
    return mapping.get(s, s if s in ("minor", "moderate", "severe") else "minor")

def _canon_location(s: str, name: Optional[str] = None) -> str:
    t = _norm(s).replace("-", " ")
    # Basic side synonyms
    t = t.replace("driver side", "left").replace("passenger side", "right")
    t = t.replace("near side", "left").replace("nearside", "left")
    t = t.replace("off side", "right").replace("offside", "right")
    t = t.replace("front end", "front").replace("rear end", "rear").replace("back", "rear")
    # Compose compound forms; include tokens inferred from the name to ensure consistency
    words = t.split()
    flags = set(words)
    if name:
        n = _norm(name).replace("-", " ")
        for w in n.split():
            if w in ("front", "rear", "left", "right"):
                flags.add(w)
    order = ["front", "rear", "left", "right"]
    composed = " ".join([w for w in order if w in flags])
    return composed if composed else t

def _canon_name(s: str) -> str:
    t = _norm(s)
    repl = [
        ("bonnet", "hood"), ("boot", "trunk"), ("windscreen", "windshield"),
        ("wing", "fender"), ("grill", "grille"), ("headlamp", "headlight"),
        ("tail lamp", "tail light"), ("taillamp", "tail light"),
        ("number plate", "license plate"), ("license-plate", "license plate"),
        ("foglamp", "fog light"), ("quarterpanel", "quarter panel"),
    ]
    for a, b in repl:
        if a in t:
            t = t.replace(a, b)
    # Additional normalizations for common misspellings and variants
    extra = [
        ("licence", "license"),
        ("number-plate", "license plate"),
        ("numberplate", "license plate"),
        ("grillee", "grille"),
    ]
    for a, b in extra:
        if a in t:
            t = t.replace(a, b)
    return t

def _canon_category(s: str) -> str:
    return _norm(s)

def canonicalize_part(p: dict) -> dict:
    q = dict(p) if isinstance(p, dict) else {}
    q["name"] = _canon_name(q.get("name", ""))
    q["location"] = _canon_location(q.get("location", ""), q.get("name", ""))
    q["category"] = _canon_category(q.get("category", ""))
    if q.get("severity") is not None:
        q["severity"] = _canon_severity(q.get("severity", ""))
    return q

def _fingerprint_images(images: List[Path]) -> str:
    """Stable fingerprint of the image set using names and sizes only (no content read)."""
    m = hashlib.sha256()
    for p in sorted(images, key=lambda x: x.name):
        try:
            size = p.stat().st_size
        except Exception:
            size = 0
        m.update(p.name.encode())
        m.update(str(size).encode())
    return m.hexdigest()

def _load_superset(path: Path) -> tuple[dict[tuple, dict], int]:
    """Return (map, run_count). Map: key(tuple)-> {"count": int, "part": dict}"""
    try:
        if not path.exists():
            return {}, 0
        data = json.loads(path.read_text())
        parts = data.get("parts", []) or []
        m: dict[tuple, dict] = {}
        for item in parts:
            part = item.get("part") or {
                "name": item.get("name", ""),
                "location": item.get("location", ""),
                "category": item.get("category", ""),
            }
            # Canonicalize legacy entries to unify keys
            part = canonicalize_part(part)
            key = _key_for_part(part)
            prev = m.get(key, {"count": 0, "part": {}})
            # Merge counts and prefer better representation
            prev["count"] = int(prev.get("count", 0)) + int(item.get("count", 0))
            prev["part"] = _prefer_part(part, prev.get("part", {}))
            m[key] = prev
        return m, int(data.get("run_count", 0))
    except Exception:
        return {}, 0

def _save_superset(path: Path, image_fingerprint: str, superset_map: dict[tuple, dict], run_count: int) -> None:
    items = []
    for key, entry in superset_map.items():
        # Key is (name, location) post-canonicalization; category is advisory and taken from the stored part
        name, location = key
        category = _norm(entry.get("part", {}).get("category", ""))
        items.append({
            "name": name,
            "location": location,
            "category": category,
            "count": int(entry.get("count", 0)),
            "part": entry.get("part", {}),
        })
    out = {
        "fingerprint": image_fingerprint,
        "run_count": run_count,
        "parts": items,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))

def _prefer_part(new: dict, base: dict) -> dict:
    """Deterministic preference: higher severity, longer description, then lexicographic tiebreaker."""
    if not base:
        return new
    ns = SEVERITY_PRIORITY_GLOBAL.get(new.get("severity", "minor"), 1)
    bs = SEVERITY_PRIORITY_GLOBAL.get(base.get("severity", "minor"), 1)
    new_desc = str(new.get("description", new.get("damage_description", "")))
    base_desc = str(base.get("description", base.get("damage_description", "")))
    if ns > bs:
        return new
    if ns < bs:
        return base
    if len(new_desc) > len(base_desc):
        return new
    if len(new_desc) < len(base_desc):
        return base
    # Deterministic lexicographic fallback
    new_key = (_norm(new.get("name", "")), _norm(new.get("location", "")), _norm(new_desc))
    base_key = (_norm(base.get("name", "")), _norm(base.get("location", "")), _norm(base_desc))
    return new if new_key < base_key else base


def dedupe_by_phash(images: List[Path], dist_thresh: int = 5) -> List[Path]:
    """Remove near-duplicates using aHash Hamming distance."""
    selected: List[Path] = []
    hashes: List[int] = []
    for p in images:
        h = ahash(p)
        is_dup = any(hamming_distance(h, hh) <= dist_thresh for hh in hashes)
        if not is_dup:
            selected.append(p)
            hashes.append(h)
    return selected


def select_diverse_top(images: List[Path], k: int, dist_thresh: int = 8) -> List[Path]:
    """Select up to k images by quality with diversity via aHash distance."""
    if k <= 0:
        return []
    # Score all, sort best-first
    scored = [(score_image(p), p) for p in images]
    scored.sort(key=lambda t: t[0], reverse=True)
    selected: List[Path] = []
    selected_hashes: List[int] = []
    for _, p in scored:
        h = ahash(p)
        if all(hamming_distance(h, sh) > dist_thresh for sh in selected_hashes):
            selected.append(p)
            selected_hashes.append(h)
        if len(selected) >= k:
            break
    # If not enough due to diversity constraint, fill with next best ignoring distance
    if len(selected) < k:
        for _, p in scored:
            if p not in selected:
                selected.append(p)
            if len(selected) >= k:
                break
    return selected

def make_crops(area: str, images: List[Path], areas_json: dict, max_px: int = 1200) -> List[Path]:
    """Return a list of Path objects: [full_frame, roi_crop] (if bbox present).
    Creates temporary JPEG crops in /tmp and returns their paths.
    """
    out: List[Path] = []
    tmp_dir = Path("/tmp/damage_crops")
    tmp_dir.mkdir(exist_ok=True)
    # Prefer images that Phase 0 associated with this area
    suspect_paths: List[Path] = []
    for item in areas_json.get("damaged_areas", []):
        if area.lower() in item.get("area", "").lower() and item.get("image_path"):
            try:
                suspect_paths.append(Path(item["image_path"]))
            except Exception:
                pass
    # De-dup suspect set and select diverse top
    base_imgs: List[Path] = []
    if suspect_paths:
        sus_dedup = dedupe_by_phash(suspect_paths)
        base_imgs = select_diverse_top(sus_dedup, k=min(3, len(sus_dedup)))
        # IMPORTANT: Do not top-up with non-suspect frames.
        # Mixing in unrelated views (e.g., rear for front-end) causes part anchoring drift.
    else:
        # Fallback: 3 best diverse images overall
        deduped = dedupe_by_phash(images)
        base_imgs = select_diverse_top(deduped, k=min(3, len(deduped)))
    print(f"      Area '{area}': using base frames -> {[p.name for p in base_imgs]}")
    # Always include the downsized full frame
    for p in base_imgs:
        out.append(p)

    # Try to find a bbox for this area from quick-detector
    for area_item in areas_json.get("damaged_areas", []):
        if area.lower() in area_item.get("area", "").lower() and area_item.get("bbox_px"):
            x1, y1, x2, y2 = area_item["bbox_px"]
            for p in base_imgs:
                img = Image.open(p).convert("RGB")
                w, h = img.size
                # clamp bbox, expand by 15%
                pad_x = int(0.15 * (x2 - x1))
                pad_y = int(0.15 * (y2 - y1))
                cx1 = max(0, x1 - pad_x)
                cy1 = max(0, y1 - pad_y)
                cx2 = min(w, x2 + pad_x)
                cy2 = min(h, y2 + pad_y)
                crop = img.crop((cx1, cy1, cx2, cy2))
                if max(crop.size) > max_px:
                    crop.thumbnail((max_px, max_px))
                out_path = tmp_dir / f"{p.stem}_{area.replace(' ','_')}_wide.jpg"
                crop.save(out_path, "JPEG", quality=90)
                out.append(out_path)
            break  # one bbox is enough
    # Add quadrant crops from the first base image to improve coverage, even when no bbox is present
    try:
        if base_imgs:
            p0 = base_imgs[0]
            img0 = Image.open(p0).convert("RGB")
            w, h = img0.size
            mx, my = w // 2, h // 2
            quads = [
                (0, 0, mx, my, "quad_tl"),
                (mx, 0, w, my, "quad_tr"),
                (0, my, mx, h, "quad_bl"),
                (mx, my, w, h, "quad_br"),
            ]
            for x1, y1, x2, y2, tag in quads:
                crop = img0.crop((x1, y1, x2, y2))
                if max(crop.size) > max_px:
                    crop.thumbnail((max_px, max_px))
                out_path = tmp_dir / f"{p0.stem}_{area.replace(' ','_')}_{tag}.jpg"
                crop.save(out_path, "JPEG", quality=90)
                out.append(out_path)
    except Exception:
        pass
    # Add an extra wide crop covering union of all bboxes for this area
    bbox_list = [item["bbox_px"] for item in areas_json.get("damaged_areas", []) if area.lower() in item.get("area", "").lower() and item.get("bbox_px")]
    if bbox_list:
        xs = [b[0] for b in bbox_list]; ys=[b[1] for b in bbox_list]
        x2s=[b[2] for b in bbox_list]; y2s=[b[3] for b in bbox_list]
        ux1, uy1, ux2, uy2 = min(xs), min(ys), max(x2s), max(y2s)
        for p in base_imgs[:1]:
            img = Image.open(p).convert("RGB")
            w, h = img.size
            pad_x = int(0.15 * (ux2 - ux1))
            pad_y = int(0.15 * (uy2 - uy1))
            cx1 = max(0, ux1 - pad_x)
            cy1 = max(0, uy1 - pad_y)
            cx2 = min(w, ux2 + pad_x)
            cy2 = min(h, uy2 + pad_y)
            # For front-end, extend crop downward by 25% image height to include bumper
            if area.lower() in ("front end", "front"):
                cy2 = min(h, cy2 + int(0.25 * h))
            crop = img.crop((cx1, cy1, cx2, cy2))
            if max(crop.size) > max_px:
                crop.thumbnail((max_px, max_px))
            out_path = tmp_dir / f"{p.stem}_{area.replace(' ','_')}_wide.jpg"
            crop.save(out_path, "JPEG", quality=90)
            out.append(out_path)
    return out

# ----------------------- Ensemble utilities ---------------------------

def iou(box_a, box_b) -> float:
    # Handle both dict and list bbox formats
    if isinstance(box_a, dict):
        xa1, ya1, wa, ha = box_a.values()
        xa2, ya2 = xa1 + wa, ya1 + ha
    else:  # list format [x1, y1, x2, y2]
        xa1, ya1, xa2, ya2 = box_a
        wa, ha = xa2 - xa1, ya2 - ya1
    
    if isinstance(box_b, dict):
        xb1, yb1, wb, hb = box_b.values()
        xb2, yb2 = xb1 + wb, yb1 + hb
    else:  # list format [x1, y1, x2, y2]
        xb1, yb1, xb2, yb2 = box_b
        wb, hb = xb2 - xb1, yb2 - yb1
    inter_x1, inter_y1 = max(xa1, xb1), max(ya1, yb1)
    inter_x2, inter_y2 = min(xa2, xb2), min(ya2, yb2)
    inter_w, inter_h = max(0, inter_x2 - inter_x1), max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    union_area = wa * ha + wb * hb - inter_area
    return inter_area / union_area if union_area else 0.0


def union_parts(runs: List[dict]) -> dict:
    # Defensive: sanitize parts
    def sanitize_parts(parts):
        safe: List[dict] = []
        for item in parts or []:
            if isinstance(item, dict):
                safe.append(canonicalize_part(item))
            elif isinstance(item, str):
                name = item.strip().lstrip("-*•").strip()
                if name:
                    safe.append(canonicalize_part({"name": name, "severity": "minor", "damage_description": ""}))
        return safe

    if not runs:
        return {"vehicle": {"make": "Unknown", "model": "Unknown", "year": 0}, "damaged_parts": []}

    # Vehicle merge preferring non-Unknown values across runs
    vehicle = {"make": "Unknown", "model": "Unknown", "year": 0}
    for k in ("make", "model", "year"):
        for run in runs:
            val = run.get("vehicle", {}).get(k)
            if val not in (None, "", "Unknown", 0):
                vehicle[k] = val
                break

    # IoU-clustered vote aggregation across runs to avoid vote inflation
    def norm(s: str) -> str:
        return (s or "").strip().lower()
    severity_priority = {"severe": 3, "moderate": 2, "minor": 1}

    # key -> list of clusters; each cluster: {"rep": dict, "runs": set[int], "bbox_px": Any, "n": int}
    clusters_by_key: dict[tuple, List[dict]] = {}

    def _get_bbox(p: dict):
        b = p.get("bbox_px")
        return b if b else None

    def _match_cluster(clusters: List[dict], cand_bbox) -> Optional[dict]:
        if not clusters:
            return None
        if cand_bbox is None:
            # match cluster with no bbox if present
            for cl in clusters:
                if cl.get("bbox_px") is None:
                    return cl
            return None
        for cl in clusters:
            cb = cl.get("bbox_px")
            if cb is None:
                continue
            try:
                if iou(cb, cand_bbox) >= CLUSTER_IOU_THRESH:
                    return cl
            except Exception:
                continue
        return None

    def _upgrade(base: dict, cand: dict) -> dict:
        base_sev = severity_priority.get(base.get("severity", "minor"), 1)
        cand_sev = severity_priority.get(cand.get("severity", "minor"), 1)
        base_desc = str(base.get("description", base.get("damage_description", "")))
        cand_desc = str(cand.get("description", cand.get("damage_description", "")))
        choose = False
        if cand_sev > base_sev:
            choose = True
        elif cand_sev == base_sev and len(cand_desc) > len(base_desc):
            choose = True
        elif cand_sev == base_sev and len(cand_desc) == len(base_desc):
            if (
                (norm(cand.get("name","")), norm(cand.get("location","")), norm(cand_desc))
                < (norm(base.get("name","")), norm(base.get("location","")), norm(base_desc))
            ):
                choose = True
        if choose:
            # Preserve existing image and bbox if missing on candidate
            if not cand.get("image") and base.get("image"):
                cand["image"] = base["image"]
            if not cand.get("bbox_px") and base.get("bbox_px"):
                cand["bbox_px"] = base.get("bbox_px")
            return cand
        return base

    for rid, run in enumerate(runs):
        for cand in sanitize_parts(run.get("damaged_parts", [])):
            key = (norm(cand.get("name", "")), norm(cand.get("location", "")))
            clusters = clusters_by_key.setdefault(key, [])
            bbox = _get_bbox(cand)
            match = _match_cluster(clusters, bbox)
            if match is None:
                rep = dict(cand)
                clusters.append({"rep": rep, "runs": set([rid]), "bbox_px": bbox, "n": 1})
            else:
                match["rep"] = _upgrade(match["rep"], cand)
                if rid not in match["runs"]:
                    match["runs"].add(rid)
                match["n"] += 1

    # Flatten clusters to parts and attach per-cluster votes (unique runs)
    parts: List[dict] = []
    for _key, clist in clusters_by_key.items():
        for cl in clist:
            part = cl["rep"]
            part["_votes"] = len(cl["runs"])  # votes = number of runs supporting this cluster
            parts.append(part)

    # Optional: filter by minimum votes to reduce single-run hallucinations.
    # In comprehensive mode, we keep low-vote items as potential_parts instead of dropping them.
    raw_parts = list(parts)
    before_cnt = len(raw_parts)
    def _thr(p):
        sev = (p.get("severity") or "minor").strip().lower()
        if sev == "severe":
            return max(1, MIN_VOTES_SEVERE)
        if sev == "moderate":
            return max(1, MIN_VOTES_MODERATE)
        return max(1, MIN_VOTES_MINOR)
    filtered = [p for p in raw_parts if int(p.get("_votes", 0)) >= max(MIN_VOTES_PER_PART, _thr(p))]
    if len(filtered) != before_cnt:
        print(f"Applied vote thresholds (global={MIN_VOTES_PER_PART}, sev={MIN_VOTES_SEVERE}, mod={MIN_VOTES_MODERATE}, min={MIN_VOTES_MINOR}): {before_cnt}->{len(filtered)} parts")
    # Compute potential from insufficient votes when in comprehensive mode
    potential_from_votes: List[dict] = []
    if COMPREHENSIVE_MODE:
        def _keyp(px: dict) -> tuple:
            return (norm(px.get("name", "")), norm(px.get("location", "")))
        def_keys = {_keyp(p) for p in filtered}
        seen_pot = set()
        for rp in raw_parts:
            k = _keyp(rp)
            if k in def_keys or k in seen_pot:
                continue
            pot = dict(rp)
            pot.setdefault("_potential_reason", "insufficient_votes")
            potential_from_votes.append(pot)
            seen_pot.add(k)
    parts = filtered

    parts.sort(key=lambda p: (
        -p.get("_votes", 0),
        -severity_priority.get(p.get("severity", "minor"), 1),
        norm(p.get("name", "")),
        norm(p.get("location", "")),
    ))

    # No cap: keep all distinct (clustered) parts
    print(f"Final merged parts (IoU-clustered @ {CLUSTER_IOU_THRESH}): {[p.get('name','Unknown') for p in parts]}")
    if COMPREHENSIVE_MODE and potential_from_votes:
        print(f"Union flagged {len(potential_from_votes)} additional candidates as potential (insufficient votes)")
        return {"vehicle": vehicle, "damaged_parts": parts, "potential_parts": potential_from_votes}
    return {"vehicle": vehicle, "damaged_parts": parts}

# ----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images_dir", required=True)
    ap.add_argument("--out", default="damage_report.json")
    ap.add_argument("--model", default="gpt-4o")
    # Optional user-provided vehicle data (CLI override)
    ap.add_argument("--vehicle_make")
    ap.add_argument("--vehicle_model")
    ap.add_argument("--vehicle_year")
    args = ap.parse_args()

    # load API key from .env if present
    load_dotenv()

    # Initialize run metrics for Railway logging
    metrics = {
        "timestamp": time.time(),
        "strict_mode": STRICT_MODE,
        "detection_temps": DETECTION_TEMPS,
        "vehicle_id": {},
        "quick": {},
        "phase1": {"tasks_total": 0, "tasks_completed": 0, "per_temp": {}, "per_area": {}, "per_prompt": {}},
        "union": {},
        "phase2_enrichment": {},
        "completeness": {},
        "verification": {},
        "final": {},
        "superset": {},
    }

    images = sorted(Path(args.images_dir).glob("*.jp*g"))
    if not images:
        sys.exit("No images in dir")
    image_fingerprint = _fingerprint_images(images)
    print(f"Image set fingerprint: {image_fingerprint[:12]}… ({len(images)} files)")
    superset_map: dict[tuple, dict] = {}
    superset_runs = 0
    superset_path = CACHE_SUPERSET_DIR / f"{image_fingerprint}.json"
    if PERSIST_MAX_UNION:
        superset_map, superset_runs = _load_superset(superset_path)
        print(f"Loaded superset with {len(superset_map)} parts across {superset_runs} runs")
        try:
            metrics["superset"]["loaded_keys"] = len(superset_map)
            metrics["superset"]["loaded_runs"] = superset_runs
        except Exception:
            pass

    # ----------------  Phase -1 – Vehicle Identification (Per-image voting)  ----------------
    def identify_vehicle_image(img: Path) -> dict:
        """Identify vehicle from a single image with deterministic, badge-aware output."""
        try:
            prompt = VEHICLE_ID_PROMPT.read_text()
            id_txt = call_openai_vision(prompt, [img], args.model, temperature=0.0, max_images=1)
            if id_txt.startswith("```"):
                id_txt = id_txt.split("```",1)[1].rsplit("```",1)[0].strip()
            id_json = json.loads(id_txt)
            veh = id_json.get("vehicle", {})
            badge = id_json.get("badge_visible", id_json.get("badgeVisible", False))
            conf = id_json.get("confidence", 0.0)
            result = {
                "make": veh.get("make", "Unknown"),
                "model": veh.get("model", "Unknown"),
                "year": veh.get("year", 0),
                "badge_visible": bool(badge),
                "confidence": float(conf) if isinstance(conf, (int, float)) else 0.0,
                "_image": img.name,
                "_path": str(img),
            }
            print(f"Vehicle ID from {img.name}: {result}")
            return result
        except Exception as e:
            print(f"Vehicle-ID for {img.name} failed: {e}")
            return {}

    # Choose up to 6 diverse images for voting
    id_candidates = select_diverse_top(dedupe_by_phash(images), k=min(6, len(images)))
    print(f"Vehicle ID on {len(id_candidates)} images: {[p.name for p in id_candidates]}")

    votes = Counter()
    field_votes = {"make": Counter(), "model": Counter(), "year": Counter()}
    per_image_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(id_candidates))) as executor:
        future_to_img = {executor.submit(identify_vehicle_image, img): img for img in id_candidates}
        for future in concurrent.futures.as_completed(future_to_img):
            img = future_to_img[future]
            try:
                res = future.result(timeout=25)
                if not res:
                    continue
                per_image_results.append(res)
                sig = (res.get("make"), res.get("model"), res.get("year"))
                weight = 1 + (1 if res.get("badge_visible") else 0) + (1 if (res.get("confidence", 0.0) >= 0.6) else 0)
                votes[sig] += weight
                for f in ("make","model","year"):
                    v = res.get(f)
                    if v not in (None, "", "Unknown", 0):
                        field_votes[f][v] += weight
            except Exception as e:
                print(f"Vehicle-ID image {img.name} timed out/failed: {e}")

    vehicle = {"make": "Unknown", "model": "Unknown", "year": 0}
    top = votes.most_common(2)
    if top:
        winner, w = top[0]
        vehicle["make"], vehicle["model"], vehicle["year"] = winner
        print(f"Vehicle consensus: {winner} (weight {w}) from {len(per_image_results)} images")
        # Tie-break if close and same make but conflicting model (e.g., 108 vs 308)
        if len(top) == 2:
            (cand2, w2) = top[1]
            if abs(w - w2) <= 2 and winner[0] == cand2[0] and winner[1] != cand2[1]:
                tb_imgs = [Path(r.get("_path")) for r in per_image_results if r.get("badge_visible")][:2]
                if not tb_imgs:
                    tb_imgs = id_candidates[:2]
                cmp_prompt = (
                    "You are an expert vehicle identifier. Decide strictly between the two candidate models for the same make.\n"
                    f"Make: {winner[0]}\n"
                    f"Candidate A: {winner[1]}\n"
                    f"Candidate B: {cand2[1]}\n"
                    "Return JSON only: {\"model\": \"A\" or \"B\", \"confidence\": 0.0-1.0}.\n"
                    "If uncertain, pick the best guess deterministically at temperature 0.\n"
                )
                try:
                    tb_txt = call_openai_vision(cmp_prompt, tb_imgs, args.model, temperature=0.0, max_images=min(2, len(tb_imgs)))
                    if tb_txt.startswith("```"):
                        tb_txt = tb_txt.split("```",1)[1].rsplit("```",1)[0].strip()
                    tb = json.loads(tb_txt)
                    pick = tb.get("model")
                    if pick == "A":
                        vehicle["model"] = winner[1]
                    elif pick == "B":
                        vehicle["model"] = cand2[1]
                    print(f"Tie-break selected model: {vehicle['model']} (A={winner[1]}, B={cand2[1]})")
                    tie_break_used = True
                except Exception as e:
                    print(f"Tie-break failed: {e}")
    else:
        # fallback by independent field votes
        for f in ("make","model","year"):
            if field_votes[f]:
                vehicle[f] = field_votes[f].most_common(1)[0][0]
    print(f"Final vehicle: {vehicle.get('make','Unknown')} {vehicle.get('model','Unknown')} {vehicle.get('year',0)}")
    # Apply CLI overrides if provided
    try:
        if getattr(args, "vehicle_make", None) or getattr(args, "vehicle_model", None) or getattr(args, "vehicle_year", None):
            if getattr(args, "vehicle_make", None):
                vehicle["make"] = args.vehicle_make
            if getattr(args, "vehicle_model", None):
                vehicle["model"] = args.vehicle_model
            if getattr(args, "vehicle_year", None):
                try:
                    vehicle["year"] = int(str(args.vehicle_year).strip())
                except Exception:
                    pass
            print(f"Vehicle overridden from CLI: {vehicle.get('make','Unknown')} {vehicle.get('model','Unknown')} {vehicle.get('year',0)}")
    except Exception as _e:
        pass

    # Vehicle-ID metrics
    try:
        total_results = len(per_image_results)
        avg_conf = (sum([float(r.get("confidence", 0.0) or 0.0) for r in per_image_results]) / total_results) if total_results else 0.0
        badge_rate = (sum([1 for r in per_image_results if r.get("badge_visible")]) / total_results) if total_results else 0.0
        metrics["vehicle_id"] = {
            "n_candidates": len(id_candidates),
            "n_success": total_results,
            "avg_confidence": round(avg_conf, 3),
            "badge_visible_rate": round(badge_rate, 3),
            "tie_break_used": bool(tie_break_used),
            "final": vehicle,
        }
    except Exception:
        pass

    # ----------------  Phase 0 – Quick Area Detection (Parallel)  -----------------
    def quick_detect_image(img, idx, prompt_text, model):
        """Quick damage detection for a single image"""
        try:
            txt = call_openai_vision(prompt_text, [img], model, temperature=0.0)
            if txt.startswith("```"):
                txt = txt.split("```",1)[1].rsplit("```",1)[0].strip()
            quick_json = json.loads(txt)
            print(f"   Image {idx+1}: quick detector success")
            # Attach source image path so we can map damaged areas -> images
            quick_json["__image_path"] = str(img)
            return quick_json
        except Exception as e:
            print(f"   Image {idx+1}: quick detection failed – {e}")
            return None
    
    quick_prompt = PHASE0_QUICK_PROMPT.read_text()
    print("Phase 0: Parallel quick damaged-area detection…")
    # Use diverse, deduplicated subset to avoid redundant views and improve coverage
    _dedup = dedupe_by_phash(images)
    quick_candidates = select_diverse_top(_dedup, k=min(8, len(_dedup)))
    max_quick_images = len(quick_candidates)
    try:
        metrics["quick"]["n_candidates"] = max_quick_images
    except Exception:
        pass
    
    # Process images in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_idx = {executor.submit(quick_detect_image, img, idx, quick_prompt, args.model): idx 
                        for idx, img in enumerate(quick_candidates)}
        # Collect results by index to preserve original order deterministically
        quick_results = {}
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                result = future.result(timeout=30)
                if result:
                    quick_results[idx] = result
            except Exception as e:
                print(f"Quick detection image {idx+1} timed out: {e}")
        quick_runs = [quick_results[i] for i in range(max_quick_images) if i in quick_results]
    if not quick_runs:
        print("   Quick detection failed for all images – running generic area detector …")
        try:
            metrics["quick"]["fallback_generic_used"] = True
        except Exception:
            pass
        try:
            generic_prompt = GENERIC_AREAS_PROMPT.read_text()
            # Limit to a representative subset to keep payload small
            generic_txt = call_openai_vision(generic_prompt, images, args.model, temperature=0.0, max_images=4)
            raw_generic = generic_txt[:400].replace("\n"," ")
            print(f"      Raw generic response (trimmed): {raw_generic}")
            if generic_txt.startswith("```"):
                generic_txt = generic_txt.split("```",1)[1].rsplit("```",1)[0].strip()
            try:
                generic_json = json.loads(generic_txt)
            except json.JSONDecodeError:
                print("      First parse failed, retrying generic detector at temp=0 …")
                generic_txt2 = call_openai_vision(generic_prompt, images, args.model, temperature=0.0, max_images=4)
                raw_generic2 = generic_txt2[:400].replace("\n"," ")
                print(f"      Retry response (trimmed): {raw_generic2}")
                try:
                    generic_json = json.loads(generic_txt2)
                except json.JSONDecodeError as e2:
                    print(f"      Generic detector parse failed twice: {e2}")
                    generic_json = {"damaged_areas": []}
            areas_json = {"vehicle": {"make": "Unknown", "model": "Unknown", "year": 0},
                          "damaged_areas": generic_json.get("damaged_areas", [])}
            if not areas_json["damaged_areas"]:
                print("   Generic detector found no damaged areas – proceeding with empty result; frontend can show warning")
        except Exception as e:
            print(f"   Generic area detection unexpected error: {e}")
            areas_json = {"vehicle": {"make": "Unknown", "model": "Unknown", "year": 0}, "damaged_areas": []}
    else:
        # Consolidate vehicle metadata
        vehicle = {"make": "Unknown", "model": "Unknown", "year": 0}
        for k in ("make", "model", "year"):
            for run in quick_runs:
                val = run.get("vehicle", {}).get(k)
                if val and val not in ("", "Unknown", 0):
                    vehicle[k] = val
                    break
        # Merge damaged areas from all quick runs
        damaged_areas_all = []
        for run in quick_runs:
            src_img = run.get("__image_path")
            for a in run.get("damaged_areas", []):
                a = dict(a)
                if src_img:
                    a["image_path"] = src_img
                damaged_areas_all.append(a)
        areas_json = {"vehicle": vehicle, "damaged_areas": damaged_areas_all}
        try:
            metrics["quick"]["n_success"] = len(quick_runs)
            metrics["quick"]["fallback_generic_used"] = False
        except Exception:
            pass



    damaged_areas = [a["area"].lower() for a in areas_json.get("damaged_areas", [])]
    if not damaged_areas:
        damaged_areas = ["front end"]
    print(f"   Detected damaged areas: {damaged_areas}")

    # ----------------  Phase 1 – Area-specialist Enterprise Detection ----
    # Prompts are designed with complementary shards - A and B cover different parts
    area_prompt_map = {
        "front end": [PROMPTS_DIR / "detect_front_A.txt", PROMPTS_DIR / "detect_front_B.txt", PHASE1_FRONT_ENTERPRISE_PROMPT],
        "front":     [PROMPTS_DIR / "detect_front_A.txt", PROMPTS_DIR / "detect_front_B.txt", PHASE1_FRONT_ENTERPRISE_PROMPT],
        "left side":  [PROMPTS_DIR / "detect_side_A.txt", PHASE1_SIDE_ENTERPRISE_PROMPT],
        "right side": [PROMPTS_DIR / "detect_side_B.txt", PHASE1_SIDE_ENTERPRISE_PROMPT],
        "side":       [PROMPTS_DIR / "detect_side_A.txt", PROMPTS_DIR / "detect_side_B.txt", PHASE1_SIDE_ENTERPRISE_PROMPT],
        "rear":       [PROMPTS_DIR / "detect_rear_A.txt", PROMPTS_DIR / "detect_rear_B.txt", PHASE1_REAR_ENTERPRISE_PROMPT],
        "rear end":   [PROMPTS_DIR / "detect_rear_A.txt", PROMPTS_DIR / "detect_rear_B.txt", PHASE1_REAR_ENTERPRISE_PROMPT],
    }    
    
    # Remove duplicate areas to prevent running same prompt combinations twice
    damaged_areas = list(dict.fromkeys(damaged_areas))  # Preserve order, remove duplicates







    def run_area_detection_task(area, prompt_path, temp, imgs_for_call, model):
        """Run a single area detection task with specific temperature"""
        try:
            prompt_text = prompt_path.read_text()
            task_id = f"{area}-{prompt_path.name}-temp{temp}"
            print(f"    Running {task_id}...")
            
            txt = call_openai_vision(prompt_text, imgs_for_call, model, temperature=temp, max_images=5)
            if txt.startswith("```"):
                if "json" in txt.split("\n")[0]:
                    txt = txt.split("\n",1)[1].rsplit("```",1)[0].strip()
                else:
                    txt = txt.split("```",1)[1].rsplit("```",1)[0].strip()
            # Robust JSON parse with fallback extraction/retry
            try:
                result = json.loads(txt)
            except json.JSONDecodeError:
                s = txt
                l = s.find("{"); r = s.rfind("}")
                parsed = None
                if l != -1 and r != -1 and r > l:
                    try:
                        parsed = json.loads(s[l:r+1])
                    except Exception:
                        parsed = None
                if parsed is None:
                    # One more attempt asking for strict JSON only
                    txt2 = call_openai_vision(prompt_text + "\nRespond with STRICTLY valid JSON only.", imgs_for_call, model, temperature=temp, max_images=5)
                    if txt2.startswith("```"):
                        if "json" in txt2.split("\n")[0]:
                            txt2 = txt2.split("\n",1)[1].rsplit("```",1)[0].strip()
                        else:
                            txt2 = txt2.split("```",1)[1].rsplit("```",1)[0].strip()
                    result = json.loads(txt2)
                else:
                    result = parsed
            combined = {
                "vehicle": result.get("vehicle", {"make": "Unknown", "model": "Unknown", "year": 0}),
                "damaged_parts": result.get("damaged_parts", [])
            }
            # Attach a stable context image to each part; override unknown/invalid names
            try:
                base_frames = [p for p in imgs_for_call if "/tmp/damage_crops" not in str(p)]
                context_img = base_frames[0] if base_frames else (imgs_for_call[0] if imgs_for_call else None)
                allowed_names = {Path(p).name for p in base_frames} if base_frames else set()
                if context_img is not None:
                    for part in combined["damaged_parts"]:
                        img_field = part.get("image")
                        if (
                            not img_field or not isinstance(img_field, str) or not img_field.strip()
                            or (allowed_names and img_field not in allowed_names)
                        ):
                            chosen = Path(context_img)
                            part["image"] = chosen.name
                            part["image_path"] = str(chosen)
            except Exception as _e:
                pass
            print(f"    ✅ {task_id}: {len(combined['damaged_parts'])} parts")
            return combined
        except Exception as e:
            print(f"    ❌ {task_id} failed: {e}")
            return None
    
    # Create all detection tasks upfront
    detection_tasks = []
    for area in damaged_areas:
        prompt_paths = area_prompt_map.get(area, [PHASE1_FRONT_ENTERPRISE_PROMPT])
        imgs_for_call = make_crops(area, images, areas_json)
        
        for prompt_path in prompt_paths:
            # Slight ensemble to increase coverage without encouraging hallucinations
            for temp in DETECTION_TEMPS:
                detection_tasks.append((area, prompt_path, temp, imgs_for_call))
    # Global enterprise sweep over diverse full frames (complements area shards)
    global_imgs = select_diverse_top(dedupe_by_phash(images), k=min(5, len(images)))
    for temp in DETECTION_TEMPS:
        detection_tasks.append(("global", PHASE1_ENTERPRISE_PROMPT, temp, global_imgs))

    print(f"Phase 1: Running {len(detection_tasks)} area-specialist + enterprise detection tasks in parallel...")
    try:
        metrics["phase1"]["tasks_total"] = len(detection_tasks)
    except Exception:
        pass
    
    # Execute all tasks in parallel with optimal thread count
    max_workers = min(8, len(detection_tasks))  # Don't overwhelm OpenAI API
    runs = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Preserve original task order deterministically
        future_to_idx = {
            executor.submit(run_area_detection_task, area, prompt_path, temp, imgs, args.model): i
            for i, (area, prompt_path, temp, imgs) in enumerate(detection_tasks)
        }
        results_by_idx = {}
        completed_count = 0
        for future in concurrent.futures.as_completed(future_to_idx):
            i = future_to_idx[future]
            area, prompt_path, temp, _imgs = detection_tasks[i]
            try:
                result = future.result(timeout=45)  # increased timeout for stability
                if result:
                    results_by_idx[i] = result
                completed_count += 1
                print(f"Progress: {completed_count}/{len(detection_tasks)} tasks completed")
                # Phase 1 metrics updates (successful tasks)
                try:
                    metrics["phase1"]["tasks_completed"] = completed_count
                    tkey = str(temp)
                    metrics["phase1"]["per_temp"][tkey] = metrics["phase1"]["per_temp"].get(tkey, 0) + 1
                    metrics["phase1"]["per_area"][area] = metrics["phase1"]["per_area"].get(area, 0) + 1
                    metrics["phase1"]["per_prompt"][prompt_path.name] = metrics["phase1"]["per_prompt"].get(prompt_path.name, 0) + 1
                except Exception:
                    pass
            except Exception as e:
                print(f"Task {area}-{prompt_path.name}-{temp} failed: {e}")
        runs = [results_by_idx[i] for i in range(len(detection_tasks)) if i in results_by_idx]

    if not runs:
        sys.exit("Enterprise detection failed for all areas")

    # Pre-union candidate metrics and vote-drop estimate
    try:
        total_raw_parts = sum(len(r.get("damaged_parts", []) or []) for r in runs)
        def _mn(s: str) -> str:
            return (s or "").strip().lower()
        pre_keys = set()
        for r in runs:
            for cand in (r.get("damaged_parts", []) or []):
                cp = canonicalize_part(cand)
                pre_keys.add((_mn(cp.get("name", "")), _mn(cp.get("location", ""))))
        metrics["union"]["pre_union_raw_parts"] = total_raw_parts
        metrics["union"]["pre_union_unique_keys"] = len(pre_keys)

        # Vote-based drop estimate mirroring union_parts
        counts = Counter()
        best_sev: dict[tuple, tuple[str, int]] = {}
        for run in runs:
            seen_in_run = set()
            for cand in (run.get("damaged_parts", []) or []):
                cp = canonicalize_part(cand)
                key = (_mn(cp.get("name", "")), _mn(cp.get("location", "")))
                if key in seen_in_run:
                    continue
                seen_in_run.add(key)
                counts[key] += 1
                cur = best_sev.get(key)
                sev = cp.get("severity", "minor")
                pr = SEVERITY_PRIORITY_GLOBAL.get(sev, 1)
                if (cur is None) or (pr > cur[1]):
                    best_sev[key] = (sev, pr)
        drop = {"severe": 0, "moderate": 0, "minor": 0}
        keep = {"severe": 0, "moderate": 0, "minor": 0}
        for k, c in counts.items():
            sev = best_sev.get(k, ("minor", 1))[0]
            thr = MIN_VOTES_SEVERE if sev == "severe" else (MIN_VOTES_MODERATE if sev == "moderate" else MIN_VOTES_MINOR)
            if int(c) >= int(thr):
                keep[sev] += 1
            else:
                drop[sev] += 1
        metrics["union"]["vote_drop_estimate"] = {"drop": drop, "keep": keep}
    except Exception:
        pass

    detected = union_parts(runs)
    try:
        metrics["union"]["iou_threshold"] = CLUSTER_IOU_THRESH
    except Exception:
        pass
    try:
        metrics["union"]["post_union_unique"] = len(detected.get("damaged_parts", []))
        sev_counts = {}
        for p in detected.get("damaged_parts", []):
            s = (p.get("severity") or "minor")
            sev_counts[s] = sev_counts.get(s, 0) + 1
        metrics["union"]["post_union_severity_dist"] = sev_counts
    except Exception:
        pass
# ---------------- vehicle back-fill from quick detector ---------------
    quick_vehicle = areas_json.get("vehicle", {})
    for k in ("make", "model", "year"):
        if detected["vehicle"].get(k, "Unknown") in ("", "Unknown", 0):
            val = quick_vehicle.get(k)
            if val not in (None, "", "Unknown", 0):
                detected["vehicle"][k] = val
    # Ensure CLI vehicle overrides take final precedence if provided
    try:
        if getattr(args, "vehicle_make", None) or getattr(args, "vehicle_model", None) or getattr(args, "vehicle_year", None):
            if getattr(args, "vehicle_make", None):
                detected["vehicle"]["make"] = args.vehicle_make
            if getattr(args, "vehicle_model", None):
                detected["vehicle"]["model"] = args.vehicle_model
            if getattr(args, "vehicle_year", None):
                try:
                    detected["vehicle"]["year"] = int(str(args.vehicle_year).strip())
                except Exception:
                    pass
    except Exception as _e:
        pass
    print(f"Detected {len(detected['damaged_parts'])} unique parts after merging")

    # Completeness pass – ask model to spot any missing parts given current list
    if ENABLE_COMPLETENESS_PASS:
        try:
            metrics["completeness"]["attempted"] = True
            metrics["completeness"]["temps_used"] = [str(t) for t in DETECTION_TEMPS]
            before_keys = { _key_for_part(canonicalize_part(p)) for p in detected.get("damaged_parts", []) }
            comp_base = PHASE1_COMPLETENESS_PROMPT.read_text()
            comp_prompt = comp_base.replace("<CURRENT_PARTS_JSON>", json.dumps(detected.get("damaged_parts", [])))
            # Build a rich image set: global diverse frames + a few area crops
            comp_imgs = list(global_imgs)
            for a in damaged_areas:
                try:
                    cimgs = make_crops(a, images, areas_json)
                    comp_imgs.extend(cimgs[:2])
                except Exception:
                    pass
            comp_imgs = dedupe_by_phash(comp_imgs)
            try:
                metrics["completeness"]["image_count"] = len(comp_imgs)
            except Exception:
                pass
            completeness_runs = []
            for temp in DETECTION_TEMPS:
                try:
                    txt = call_openai_vision(comp_prompt, comp_imgs, args.model, temperature=temp, max_images=6)
                    if txt.startswith("```"):
                        if "json" in txt.split("\n")[0]:
                            txt = txt.split("\n",1)[1].rsplit("```",1)[0].strip()
                        else:
                            txt = txt.split("```",1)[1].rsplit("```",1)[0].strip()
                    try:
                        parsed = json.loads(txt)
                    except json.JSONDecodeError:
                        s = txt; l = s.find("{"); r = s.rfind("}")
                        if l != -1 and r != -1 and r > l:
                            parsed = json.loads(s[l:r+1])
                        else:
                            raise
                    completeness_runs.append({
                        "vehicle": detected.get("vehicle", {"make":"Unknown","model":"Unknown","year":0}),
                        "damaged_parts": parsed.get("damaged_parts", [])
                    })
                except Exception as _e:
                    print(f"Completeness pass temp={temp} failed: {_e}")
            try:
                metrics["completeness"]["runs"] = len(completeness_runs)
            except Exception:
                pass
            if completeness_runs:
                runs2 = runs + completeness_runs
                detected2 = union_parts(runs2)
                after_keys = { _key_for_part(canonicalize_part(p)) for p in detected2.get("damaged_parts", []) }
                added = after_keys - before_keys
                if added:
                    print(f"Completeness pass added {len(added)} new unique parts")
                try:
                    metrics["completeness"]["added_count"] = len(added)
                    metrics["completeness"]["added_keys"] = [f"{k[0]}|{k[1]}" for k in added]
                except Exception:
                    pass
                detected = detected2
        except Exception as _e:
            print(f"Completeness pass error: {_e}")

    # Accumulate into persistent superset to maximize unique parts across runs
    if PERSIST_MAX_UNION:
        # Merge current parts into superset (increment counts for current keys only)
        for part in detected["damaged_parts"]:
            k = _key_for_part(part)
            entry = superset_map.get(k, {"count": 0, "part": {}})
            # choose better representation
            entry["part"] = _prefer_part(part, entry.get("part", {}))
            entry["count"] = int(entry.get("count", 0)) + 1
            superset_map[k] = entry
        # Build accumulated list honoring min support (default 1)
        accumulated = [
            (k, v) for k, v in superset_map.items()
            if int(v.get("count", 0)) >= max(1, PERSIST_MIN_SUPPORT)
        ]
        # Deterministic order: by count desc, severity desc, name asc
        def _sev(p: dict) -> int:
            return SEVERITY_PRIORITY_GLOBAL.get(p.get("severity", "minor"), 1)
        accumulated.sort(key=lambda kv: (-int(kv[1].get("count", 0)), -_sev(kv[1]["part"]), kv[0][0]))
        detected["damaged_parts"] = [v["part"] for _, v in accumulated]
        print(f"Accumulated superset now has {len(detected['damaged_parts'])} parts (min_support={PERSIST_MIN_SUPPORT})")

        # Phase 2 – Describe --------------------------------------------------
    # Snapshot before Phase 2 enrichment to measure deltas
    try:
        pre_p2_parts = [canonicalize_part(deepcopy(p)) for p in detected.get("damaged_parts", [])]
    except Exception:
        pre_p2_parts = detected.get("damaged_parts", [])

    p2_base = PHASE2_PROMPT.read_text()
    p2_prompt = p2_base.replace("<DETECTED_PARTS_JSON>", json.dumps(detected["damaged_parts"]))
    print("Phase 2: describing parts…")
    desc_txt = call_openai_text(p2_prompt, args.model, temperature=0.0)
    if desc_txt.startswith("```"):
        desc_txt = desc_txt.split("\n",1)[1].rsplit("```",1)[0].strip()
    desc_json = json.loads(desc_txt)
    # Merge Phase 2 descriptions into existing parts; also append any truly new parts from Phase 2
    try:
        enriched_raw = desc_json.get("damaged_parts", []) or []
        # Canonicalize enriched parts and index by (name, location)
        def norm(s: str) -> str:
            return (s or "").strip().lower()
        idx: dict[tuple, dict] = {}
        for p in enriched_raw:
            p = canonicalize_part(p)
            k = (_norm(p.get("name","")), _norm(p.get("location","")))
            if k not in idx:
                idx[k] = p
            else:
                # Prefer better representation across duplicates from Phase 2
                idx[k] = _prefer_part(p, idx[k])
        existing_keys = set()
        for part in detected["damaged_parts"]:
            # Ensure canonical
            cp = canonicalize_part(part)
            part.update(cp)
            key = (_norm(part.get("name","")), _norm(part.get("location","")))
            existing_keys.add(key)
            add = idx.get(key)
            if add:
                # Upgrade severity only if higher; description/notes if longer
                # Severity
                cur_s = SEVERITY_PRIORITY_GLOBAL.get(part.get("severity","minor"), 1)
                add_s = SEVERITY_PRIORITY_GLOBAL.get(add.get("severity","minor"), 1)
                if add_s > cur_s:
                    part["severity"] = add.get("severity")
                # Descriptive fields
                for field in ("description","notes"):
                    cur = str(part.get(field, ""))
                    new = str(add.get(field, ""))
                    if len(new) > len(cur):
                        part[field] = new
                # Other fields if present and empty
                for field in ("damage_type","repair_method"):
                    if part.get(field) in (None, "") and add.get(field) not in (None, ""):
                        part[field] = add.get(field)
        # Optionally append truly new parts discovered in Phase 2 (guarded by env)
        if PHASE2_ALLOW_NEW_PARTS:
            for k, p in idx.items():
                if k not in existing_keys:
                    detected["damaged_parts"].append(p)
    except Exception as _e:
        # Fallback: keep original parts as-is
        pass

    # Phase 2 enrichment metrics
    try:
        def _nm(s: str) -> str:
            return (s or "").strip().lower()
        pre_map = {(_nm(p.get("name", "")), _nm(p.get("location", ""))): p for p in (pre_p2_parts or [])}
        post_map = {(_nm(p.get("name", "")), _nm(p.get("location", ""))): p for p in (detected.get("damaged_parts", []) or [])}
        sev_up = 0
        desc_up = 0
        notes_up = 0
        for k, post in post_map.items():
            pre = pre_map.get(k)
            if not pre:
                continue
            if SEVERITY_PRIORITY_GLOBAL.get(post.get("severity", "minor"), 1) > SEVERITY_PRIORITY_GLOBAL.get(pre.get("severity", "minor"), 1):
                sev_up += 1
            if len(str(post.get("description", ""))) > len(str(pre.get("description", ""))):
                desc_up += 1
            if len(str(post.get("notes", ""))) > len(str(pre.get("notes", ""))):
                notes_up += 1
        appended_new = sum(1 for k in post_map.keys() if k not in pre_map)
        metrics["phase2_enrichment"] = {
            "severity_upgrades": sev_up,
            "description_upgrades": desc_up,
            "notes_upgrades": notes_up,
            "appended_new_parts": appended_new,
            "allow_new_parts": bool(PHASE2_ALLOW_NEW_PARTS),
        }
    except Exception:
        pass

    # Phase 2.5 – Verification (reduce hallucinations) ---------------------
    if ENABLE_VERIFICATION_PASS and detected.get("damaged_parts"):
        try:
            print("Phase 2.5: verifying candidate parts…")
            verifier_base = PHASE5_VERIFY_PROMPT.read_text()
            
            def _areas_for_part(p: dict) -> List[str]:
                loc = (p.get("location", "") or "").strip().lower()
                areas: List[str] = []
                if "front" in loc:
                    areas.append("front")
                if ("rear" in loc) or ("back" in loc):
                    areas.append("rear")
                if "left" in loc:
                    areas.append("left side")
                if "right" in loc:
                    areas.append("right side")
                if not areas:
                    areas = ["front"]
                # de-dup preserving order
                seen = set(); out = []
                for a in areas:
                    if a not in seen:
                        out.append(a); seen.add(a)
                return out
            
            def _gather_imgs(p: dict) -> List[Path]:
                imgs: List[Path] = []
                try:
                    for area in _areas_for_part(p):
                        try:
                            imgs.extend(make_crops(area, images, areas_json)[:3])
                        except Exception:
                            pass
                    if not imgs:
                        imgs.extend(global_imgs)
                    imgs = dedupe_by_phash(imgs)
                    imgs = select_diverse_top(imgs, k=min(5, len(imgs)))
                except Exception:
                    imgs = list(global_imgs)
                return imgs
            
            def verify_one(p: dict) -> tuple[bool, float, dict]:
                def _sev_thr(pp: dict) -> float:
                    s = (pp.get("severity") or "minor").strip().lower()
                    if s == "severe":
                        return VERIFY_CONF_SEVERE
                    if s == "moderate":
                        return VERIFY_CONF_MODERATE
                    return VERIFY_CONF_MINOR

                def _consensus_required(pp: dict) -> int:
                    s = (pp.get("severity") or "minor").strip().lower()
                    if s == "severe":
                        return max(1, VERIFY_REQUIRE_PASSES_SEVERE)
                    if s == "moderate":
                        return max(1, VERIFY_REQUIRE_PASSES_MODERATE)
                    return max(1, VERIFY_REQUIRE_PASSES_MINOR)

                imgs = _gather_imgs(p)
                # Build base and paraphrased prompts
                ptxt1 = verifier_base.replace("<CANDIDATE_PART_JSON>", json.dumps(p))
                ptxt2 = ptxt1 + "\nUse a different reasoning style to double-check. Reply with JSON only."
                temps = list(VERIFY_TEMPS) if VERIFY_TEMPS else [0.0, 0.2]
                if len(temps) < 2:
                    temps = temps + temps  # duplicate if only one provided
                prompts = [ptxt1, ptxt2]
                passes = []
                for i in range(2):
                    try:
                        txt = call_openai_vision(prompts[i], imgs, args.model, temperature=float(temps[i]), max_images=min(5, len(imgs)))
                        if txt.startswith("```"):
                            if "json" in txt.split("\n")[0]:
                                txt = txt.split("\n",1)[1].rsplit("```",1)[0].strip()
                            else:
                                txt = txt.split("```",1)[1].rsplit("```",1)[0].strip()
                        try:
                            data = json.loads(txt)
                        except json.JSONDecodeError:
                            s = txt; l = s.find("{"); r = s.rfind("}")
                            if l != -1 and r != -1 and r > l:
                                data = json.loads(s[l:r+1])
                            else:
                                raise
                        present = bool(data.get("present", False))
                        conf_val = data.get("confidence", 0.0)
                        conf = float(conf_val) if isinstance(conf_val, (int, float)) else 0.0
                        passes.append({"present": present, "confidence": conf, "temp": float(temps[i])})
                    except Exception as e:
                        print(f"Verification pass {i+1} error for {p.get('name','?')}@{p.get('location','?')}: {e}")
                        passes.append({"present": False, "confidence": 0.0, "temp": float(temps[i])})

                thr = _sev_thr(p)
                votes_yes = sum(1 for r in passes if r["present"] and r["confidence"] >= thr)
                required = _consensus_required(p)
                kept = votes_yes >= required
                best_conf = max((r["confidence"] for r in passes), default=0.0)
                evidence = {
                    "images": [Path(i).name for i in imgs],
                    "passes": passes,
                    "threshold": thr,
                    "votes_yes": votes_yes,
                    "consensus_required": required,
                }
                return kept, best_conf, evidence
            
            kept: List[dict] = []
            dropped: List[tuple] = []  # (part, conf, evidence)
            kept_confs: List[float] = []
            dropped_confs: List[float] = []
            kept_by_sev = {"severe": 0, "moderate": 0, "minor": 0}
            dropped_by_sev = {"severe": 0, "moderate": 0, "minor": 0}
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(detected["damaged_parts"]))) as ex:
                fut_map = {ex.submit(verify_one, p): p for p in detected["damaged_parts"]}
                for fut in concurrent.futures.as_completed(fut_map):
                    p = fut_map[fut]
                    try:
                        ok, conf, ev = fut.result(timeout=45)
                    except Exception:
                        ok, conf, ev = False, 0.0, {}
                    if ok:
                        kept.append(p)
                        kept_confs.append(float(conf))
                        try:
                            p["_verify"] = ev
                        except Exception:
                            pass
                        sevk = (p.get("severity") or "minor").strip().lower()
                        if sevk in kept_by_sev:
                            kept_by_sev[sevk] += 1
                    else:
                        dropped.append((p, conf, ev))
                        dropped_confs.append(float(conf))
                        sevd = (p.get("severity") or "minor").strip().lower()
                        if sevd in dropped_by_sev:
                            dropped_by_sev[sevd] += 1
            if dropped:
                for p, conf, _ in dropped:
                    print(f"❌ Verification dropped: {p.get('name','Unknown')} @ {p.get('location','')} (conf={conf:.2f})")
            print(f"Verification kept {len(kept)}/{len(detected['damaged_parts'])} parts (threshold={VERIFY_MIN_CONFIDENCE})")
            detected["damaged_parts"] = kept
            # In comprehensive mode, merge verification-dropped as potential along with any union-derived potential
            if COMPREHENSIVE_MODE:
                def _nm(s: str) -> str:
                    return (s or "").strip().lower()
                def _k(px: dict) -> tuple:
                    return (_nm(px.get("name", "")), _nm(px.get("location", "")))
                kept_keys = {_k(p) for p in kept}
                # Start with any existing union potential
                potential = []
                existing = detected.get("potential_parts", []) or []
                for pp in existing:
                    if _k(pp) not in kept_keys:
                        potential.append(pp)
                # Add verification-dropped with evidence
                for p, conf, ev in dropped:
                    if _k(p) in kept_keys:
                        continue
                    pot = dict(p)
                    try:
                        pot["_verify"] = ev
                    except Exception:
                        pass
                    pot.setdefault("_potential_reason", "verification_failed")
                    potential.append(pot)
                # Deduplicate potential by (name, location)
                uniq = {}
                for pp in potential:
                    uniq[_k(pp)] = pp
                detected["potential_parts"] = list(uniq.values())
            # Verification metrics
            try:
                kept_n = len(kept)
                total_n = kept_n + len(dropped)
                avg_kept = (sum(kept_confs) / kept_n) if kept_n else 0.0
                avg_drop = (sum(dropped_confs) / len(dropped)) if dropped_confs else 0.0
                metrics["verification"] = {
                    "threshold": VERIFY_MIN_CONFIDENCE,
                    "kept": kept_n,
                    "dropped": len(dropped),
                    "kept_rate": (kept_n / total_n) if total_n else 0.0,
                    "avg_conf_kept": round(avg_kept, 3),
                    "avg_conf_dropped": round(avg_drop, 3),
                    "severity_thresholds": {
                        "severe": VERIFY_CONF_SEVERE,
                        "moderate": VERIFY_CONF_MODERATE,
                        "minor": VERIFY_CONF_MINOR,
                    },
                    "by_severity": {
                        "kept": kept_by_sev,
                        "dropped": dropped_by_sev,
                    },
                    "consensus_required": {
                        "severe": VERIFY_REQUIRE_PASSES_SEVERE,
                        "moderate": VERIFY_REQUIRE_PASSES_MODERATE,
                        "minor": VERIFY_REQUIRE_PASSES_MINOR,
                    },
                }
            except Exception:
                pass
        except Exception as _e:
            print(f"Verification pass error: {_e}")

    # Phase 3 – Plan parts -------------------------------------------------
    p3_base = PHASE3_PROMPT.read_text()
    p3_prompt = p3_base.replace("<DETECTED_PARTS_JSON>", json.dumps(detected["damaged_parts"]))
    print("Phase 3: planning repair parts…")
    parts_txt = call_openai_text(p3_prompt, args.model, temperature=0.0)
    if parts_txt.startswith("```"):
        parts_txt = parts_txt.split("\n",1)[1].rsplit("```",1)[0].strip()
    parts_json = json.loads(parts_txt)
    detected["repair_parts"] = parts_json.get("repair_parts", [])

    # Phase 4 – Summary ----------------------------------------------------
    p4_base = PHASE4_PROMPT.read_text()
    p4_prompt = p4_base.replace("<FULL_REPORT_JSON>", json.dumps(detected))
    print("Phase 4: summarising…")
    summary_txt = call_openai_text(p4_prompt, args.model, temperature=0.0)
    if summary_txt.startswith("```"):
        summary_txt = summary_txt.split("\n",1)[1].rsplit("```",1)[0].strip()
    detected["summary"] = json.loads(summary_txt)

    pre_final_count = len(detected["damaged_parts"])
    # FINAL DUPLICATE CLEANUP - keep list stable; only drop exact duplicates
    final_parts = []
    seen_keys = set()
    
    def norm(s: str) -> str:
        return (s or "").strip().lower()
    
    for part in detected["damaged_parts"]:
        key = (norm(part.get("name", "")), norm(part.get("location", "")))
        if key in seen_keys:
            print(f"❌ DUPLICATE REMOVED (exact): {part.get('name','Unknown')} @ {part.get('location','')}")
            continue
        final_parts.append(part)
        seen_keys.add(key)
        print(f"✅ Keeping: {part.get('name', 'Unknown')}")
    
    detected["damaged_parts"] = final_parts
    # Final cleanup for potential parts: remove duplicates and any that are now definitive
    if COMPREHENSIVE_MODE:
        try:
            def _nl(s: str) -> str:
                return (s or "").strip().lower()
            keep_keys = {( _nl(p.get('name','')) , _nl(p.get('location','')) ) for p in final_parts}
            pot_final = []
            seen_p = set()
            for pp in (detected.get("potential_parts", []) or []):
                k = (_nl(pp.get('name','')), _nl(pp.get('location','')))
                if (k in keep_keys) or (k in seen_p):
                    continue
                pot_final.append(pp)
                seen_p.add(k)
            detected["potential_parts"] = pot_final
        except Exception:
            pass
    print(f"Final cleanup: {len(final_parts)} unique parts remaining")
    # Final metrics and completeness retention
    try:
        duplicates_removed = pre_final_count - len(final_parts)
        metrics["final"]["duplicates_removed"] = duplicates_removed
        metrics["final"]["n_parts"] = len(final_parts)
        if COMPREHENSIVE_MODE:
            metrics["final"]["n_potential_parts"] = len(detected.get("potential_parts", []) or [])
        sdist = {}
        for p in final_parts:
            s = (p.get("severity") or "minor")
            sdist[s] = sdist.get(s, 0) + 1
        metrics["final"]["severity_dist"] = sdist
        # Retention of completeness-added keys after verification & cleanup
        comp_added = set(metrics.get("completeness", {}).get("added_keys", []) or [])
        if comp_added:
            def _nl(s: str) -> str:
                return (s or "").strip().lower()
            final_key_strings = {f"{_nl(p.get('name',''))}|{_nl(p.get('location',''))}" for p in final_parts}
            retained = len(final_key_strings & comp_added)
            total_added = len(comp_added)
            metrics["completeness"]["retained_after_verification"] = retained
            metrics["completeness"]["retained_rate_after_verification"] = (retained / total_added) if total_added else 0.0
    except Exception:
        pass

    # Persist superset with enriched final parts
    if PERSIST_MAX_UNION:
        for part in final_parts:
            k = _key_for_part(part)
            entry = superset_map.get(k, {"count": 0, "part": {}})
            entry["part"] = _prefer_part(part, entry.get("part", {}))
            superset_map[k] = entry
        try:
            _save_superset(superset_path, image_fingerprint, superset_map, superset_runs + 1)
            print(f"Saved superset: {superset_path.name} with {len(superset_map)} keys")
            try:
                metrics["superset"]["final_keys"] = len(superset_map)
            except Exception:
                pass
        except Exception as e:
            print(f"Warning: failed to save superset: {e}")

    report = dict(detected)
    # Attach configuration snapshot for auditability
    try:
        report["_config"] = {
            "comprehensive_mode": COMPREHENSIVE_MODE,
            "strict_mode": STRICT_MODE,
            "detection_temps": [float(t) for t in DETECTION_TEMPS],
            "cluster_iou_thresh": CLUSTER_IOU_THRESH,
            "min_votes": {
                "per_part": MIN_VOTES_PER_PART,
                "severe": MIN_VOTES_SEVERE,
                "moderate": MIN_VOTES_MODERATE,
                "minor": MIN_VOTES_MINOR,
            },
            "verification": {
                "enabled": ENABLE_VERIFICATION_PASS,
                "temps": [float(t) for t in VERIFY_TEMPS],
                "conf_thresholds": {
                    "severe": VERIFY_CONF_SEVERE,
                    "moderate": VERIFY_CONF_MODERATE,
                    "minor": VERIFY_CONF_MINOR,
                },
                "consensus_required": {
                    "severe": VERIFY_REQUIRE_PASSES_SEVERE,
                    "moderate": VERIFY_REQUIRE_PASSES_MODERATE,
                    "minor": VERIFY_REQUIRE_PASSES_MINOR,
                },
            },
            "completeness_pass": ENABLE_COMPLETENESS_PASS,
            "phase2_allow_new_parts": PHASE2_ALLOW_NEW_PARTS,
            "persist_max_union": PERSIST_MAX_UNION,
            "persist_min_support": PERSIST_MIN_SUPPORT,
            "model": getattr(args, "model", "gpt-4o"),
            "max_damaged_parts_cap": MAX_DAMAGED_PARTS,
        }
    except Exception:
        pass

    # Write the report to file
    Path(args.out).write_text(json.dumps(report, indent=2))
    print(f"Final report written to {args.out}")

    # Summarize metrics for Railway logs
    try:
        print("\n=== METRICS SUMMARY (Railway) ===")
        print(f" - strict_mode={metrics.get('strict_mode')} temps={metrics.get('detection_temps')}")
        u = metrics.get("union", {})
        print(f" - pre_union_raw={u.get('pre_union_raw_parts')} unique={u.get('pre_union_unique_keys')}")
        vdrop = (u.get("vote_drop_estimate") or {}).get("drop", {})
        print(f" - vote_drop_estimate: severe={vdrop.get('severe',0)} moderate={vdrop.get('moderate',0)} minor={vdrop.get('minor',0)}")
        print(f" - post_union_unique={u.get('post_union_unique')} sev_dist={u.get('post_union_severity_dist')}")
        ver = metrics.get("verification", {})
        if ver:
            print(f" - verification: kept={ver.get('kept')} dropped={ver.get('dropped')} kept_rate={round(ver.get('kept_rate',0.0),3)} avg_kept={ver.get('avg_conf_kept')} avg_drop={ver.get('avg_conf_dropped')} thr={ver.get('threshold')}")
        comp = metrics.get("completeness", {})
        if comp:
            print(f" - completeness: runs={comp.get('runs')} added={comp.get('added_count')} retained={comp.get('retained_after_verification',0)}")
        fin = metrics.get("final", {})
        if COMPREHENSIVE_MODE:
            print(f" - final: n_parts={fin.get('n_parts')} n_potential={fin.get('n_potential_parts')} duplicates_removed={fin.get('duplicates_removed')}")
        else:
            print(f" - final: n_parts={fin.get('n_parts')} duplicates_removed={fin.get('duplicates_removed')}")
        # Emit machine-parsable JSON on a single line for log collection
        try:
            print("METRICS_JSON " + json.dumps(metrics))
        except Exception as _e:
            print(f"METRICS_JSON serialization error: {_e}")
    except Exception:
        pass

    # Upload to storage and notify webhook if running in production
    if os.getenv("RAILWAY_ENVIRONMENT") == "production":
        try:
            import requests
            from datetime import datetime
            
            # Generate unique filenames with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            report_id = os.path.splitext(os.path.basename(args.out))[0]
            
            # Upload JSON report
            json_filename = f"reports/{report_id}_{timestamp}.json"
            json_url = upload_to_supabase_storage(args.out, json_filename)
            
            # Generate and upload PDF
            pdf_path = args.out.replace('.json', '.pdf')
            generate_pdf(report, pdf_path)  # Assuming you have this function
            pdf_filename = f"reports/{report_id}_{timestamp}.pdf"
            pdf_url = upload_to_supabase_storage(pdf_path, pdf_filename)
            
            # Notify webhook
            webhook_url = f"{os.getenv('SUPABASE_URL')}/functions/v1/report-complete"
            response = requests.post(
                webhook_url,
                json={
                    "document_id": report_id,
                    "json_url": json_url,
                    "pdf_url": pdf_url
                },
                headers={
                    "Authorization": f"Bearer {os.getenv('SUPABASE_SERVICE_ROLE_KEY')}",
                    "Content-Type": "application/json"
                },
                timeout=10
            )
            print(f"Webhook notification sent: {response.status_code}")
            
        except Exception as e:
            print(f"Warning: Webhook notification failed: {str(e)}")
            # Don't fail the whole process if webhook fails

def upload_to_supabase_storage(file_path: str, destination_path: str) -> Optional[str]:
    """Upload a file to Supabase Storage and return its public URL."""
    try:
        # Get environment variables
        supabase_url = os.getenv("SUPABASE_URL")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not service_role_key:
            print("Error: Missing Supabase credentials")
            return None
            
        # Read file content
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Upload file to Supabase Storage
        upload_url = f"{supabase_url}/storage/v1/object/auto-damage-reports/{destination_path}"
        headers = {
            'Authorization': f'Bearer {service_role_key}',
            'Content-Type': 'application/octet-stream',
            'x-upsert': 'true'
        }
        
        response = requests.put(
            upload_url,
            headers=headers,
            data=file_content
        )
        
        if response.status_code not in (200, 201):
            print(f"Error uploading {file_path}: {response.status_code} - {response.text}")
            return None
            
        # Return public URL
        return f"{supabase_url}/storage/v1/object/public/auto-damage-reports/{destination_path}"
        
    except Exception as e:
        print(f"Error in upload_to_supabase_storage: {str(e)}")
        return None

def generate_pdf(report_data: dict, output_path: str) -> bool:
    """Generate a PDF from the report data.
    
    This is a placeholder - implement your PDF generation logic here.
    For now, we'll just create an empty file.
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Create empty file as placeholder
        with open(output_path, 'wb') as f:
            f.write(b'PDF generation would go here')
        return True
    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        return False

if __name__ == "__main__":
    main()
