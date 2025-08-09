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


# ----------------------- YOLO integration disabled -------------------
# placeholder no-op

# ----------------------- OpenAI client tuning -------------------------
# Global retry/backoff and concurrency limits to reduce failures and load
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "3"))
OPENAI_BACKOFF_BASE = float(os.getenv("OPENAI_BACKOFF_BASE", "0.5"))  # seconds
OPENAI_CONCURRENCY = int(os.getenv("OPENAI_CONCURRENCY", "4"))
_openai_sem = threading.Semaphore(OPENAI_CONCURRENCY)

def get_candidate_boxes(img_path: Path):
    """Return empty list – YOLO disabled."""
    return []
    global _yolo_model
    if _yolo_model is None:
        # Allow Ultralytics model class through PyTorch safe loader (torch >=2.6)
        try:
            import torch, ultralytics.nn.tasks as t
            if hasattr(torch.serialization, "add_safe_globals"):
                torch.serialization.add_safe_globals({t.DetectionModel})
        except Exception:
            pass
        _yolo_model = YOLO("yolov8n.pt")  # small model
    return _yolo_model


def get_candidate_boxes(img_path: Path):
    model = get_yolo_model()
    results = model(str(img_path), conf=0.25, iou=0.5, max_det=20, verbose=False)[0]
    boxes = []
    for b in results.boxes.xyxy.cpu().numpy():
        x1, y1, x2, y2 = b[:4]
        boxes.append({"bbox_px": {"x": int(x1), "y": int(y1), "w": int(x2-x1), "h": int(y2-y1)}})
    return boxes

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
                out_path = tmp_dir / f"{p.stem}_{area.replace(' ','_')}_crop.jpg"
                crop.save(out_path, "JPEG", quality=90)
                out.append(out_path)
            break  # one bbox is enough
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
    # Defensive: sanitize runs and their damaged_parts before merging
    def sanitize_parts(parts):
        safe: List[dict] = []
        for item in parts or []:
            if isinstance(item, dict):
                safe.append(item)
            elif isinstance(item, str):
                name = item.strip().lstrip("-*•").strip()
                if name:
                    safe.append({
                        "name": name,
                        "severity": "minor",
                        "damage_description": "",
                    })
            # else: ignore non-supported types
        return safe

    if not runs:
        return {"vehicle": {"make": "Unknown", "model": "Unknown", "year": 0}, "damaged_parts": []}

    # Deepcopy first run and sanitize its parts
    merged = deepcopy(runs[0])
    merged["damaged_parts"] = sanitize_parts(merged.get("damaged_parts", []))
    # merge vehicle metadata preferring non-Unknown values
    for k in ("make","model","year"):
        if merged.get("vehicle",{}).get(k,"Unknown") in ("", "Unknown"):
            for run in runs[1:]:
                val = run.get("vehicle",{}).get(k,"")
                if val and val.lower() != "unknown":
                    merged.setdefault("vehicle",{})[k]=val
                    break
    
    # Enterprise-grade intelligent duplicate merging
    for run in runs[1:]:
        cand_list = sanitize_parts(run.get("damaged_parts", []))
        for cand in cand_list:
            duplicate = False
            for i, base in enumerate(list(merged["damaged_parts"])):
                if not isinstance(base, dict):
                    # Coerce or skip unexpected base types
                    base = {"name": str(base), "severity": "minor", "damage_description": ""}
                    merged["damaged_parts"][i] = base
                # Normalize part names for comparison
                cand_name = cand.get("name", "").lower().strip()
                base_name = base.get("name", "").lower().strip()
                cand_location = cand.get("location", "").lower().strip()
                base_location = base.get("location", "").lower().strip()
                
                # ENHANCED DUPLICATE DETECTION:
                # 1. Exact name match
                # 2. Fuzzy name match (e.g., "Front Bumper Cover" vs "Front Bumper")
                # 3. Same location + similar category
                
                is_duplicate = False
                
                # Exact match
                if cand_name == base_name:
                    is_duplicate = True
                # Fuzzy match - one name contains the other
                elif (cand_name in base_name or base_name in cand_name) and len(cand_name) > 3 and len(base_name) > 3:
                    is_duplicate = True
                # Location + category match (for parts like "Left Front Fender" vs "Left Fender")
                elif (cand_location == base_location and cand_location and 
                      cand.get("category") == base.get("category") and
                      ("fender" in cand_name and "fender" in base_name or
                       "bumper" in cand_name and "bumper" in base_name or
                       "headlight" in cand_name and "headlight" in base_name)):
                    is_duplicate = True
                
                if is_duplicate:
                    
                    # ENTERPRISE MERGING LOGIC:
                    # 1. Severity hierarchy: severe > moderate > minor
                    # 2. More detailed descriptions preferred
                    # 3. Better bounding box coordinates preferred
                    
                    cand_severity = cand.get("severity", "minor")
                    base_severity = base.get("severity", "minor")
                    severity_priority = {"severe": 3, "moderate": 2, "minor": 1}
                    
                    cand_desc_length = len(cand.get("damage_description", ""))
                    base_desc_length = len(base.get("damage_description", ""))
                    
                    should_upgrade = False
                    upgrade_reason = ""
                    
                    # Check if candidate is better
                    if severity_priority.get(cand_severity, 1) > severity_priority.get(base_severity, 1):
                        should_upgrade = True
                        upgrade_reason = f"severity upgrade ({base_severity} → {cand_severity})"
                    elif (severity_priority.get(cand_severity, 1) == severity_priority.get(base_severity, 1) and 
                          cand_desc_length > base_desc_length):
                        should_upgrade = True
                        upgrade_reason = "more detailed description"
                    
                    if should_upgrade:
                        merged["damaged_parts"][i] = cand
                        print(f"Upgraded {cand.get('name', 'Unknown')}: {upgrade_reason}")
                    else:
                        print(f"Kept existing {base.get('name', 'Unknown')} detection (better quality)")
                    
                    duplicate = True
                    break
                    
            if not duplicate:
                merged["damaged_parts"].append(cand)
                print(f"Added new part: {cand.get('name', 'Unknown')} ({cand.get('severity', 'unknown')} at {cand.get('location', 'unknown')})")
    
    print(f"Final merged parts: {[p.get('name', 'Unknown') for p in merged['damaged_parts']]}")
    return merged

# ----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images_dir", required=True)
    ap.add_argument("--out", default="damage_report.json")
    ap.add_argument("--model", default="gpt-4o")
    args = ap.parse_args()

    # load API key from .env if present
    load_dotenv()

    images = sorted(Path(args.images_dir).glob("*.jp*g"))
    if not images:
        sys.exit("No images in dir")

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
                except Exception as e:
                    print(f"Tie-break failed: {e}")
    else:
        # fallback by independent field votes
        for f in ("make","model","year"):
            if field_votes[f]:
                vehicle[f] = field_votes[f].most_common(1)[0][0]
    print(f"Final vehicle: {vehicle.get('make','Unknown')} {vehicle.get('model','Unknown')} {vehicle.get('year',0)}")

    # ----------------  Phase 0 – Quick Area Detection (Parallel)  -----------------
    def quick_detect_image(img, idx, prompt, model):
        """Quick damage detection for a single image"""
        try:
            quick_txt = call_openai_vision(prompt, [img], model, temperature=0.3)
            if quick_txt.startswith("```"):
                quick_txt = quick_txt.split("```",1)[1].rsplit("```",1)[0].strip()
            quick_json = json.loads(quick_txt)
            print(f"   Image {idx+1}: quick detector success")
            # Attach source image path so we can map damaged areas -> images
            quick_json["__image_path"] = str(img)
            return quick_json
        except Exception as e:
            print(f"   Image {idx+1}: quick detection failed – {e}")
            return None
    
    quick_prompt = PHASE0_QUICK_PROMPT.read_text()
    print("Phase 0: Parallel quick damaged-area detection…")
    max_quick_images = min(8, len(images))  # safety cap to avoid excessive cost
    
    # Process images in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_idx = {executor.submit(quick_detect_image, img, idx, quick_prompt, args.model): idx 
                        for idx, img in enumerate(images[:max_quick_images])}
        
        quick_runs = []
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                result = future.result(timeout=20)  # 20 second timeout per image
                if result:  # Only add successful results
                    quick_runs.append(result)
            except Exception as e:
                print(f"Quick detection image {idx+1} timed out: {e}")
    if not quick_runs:
        print("   Quick detection failed for all images – running generic area detector …")
        try:
            generic_prompt = GENERIC_AREAS_PROMPT.read_text()
            # Limit to a representative subset to keep payload small
            generic_txt = call_openai_vision(generic_prompt, images, args.model, temperature=0.3, max_images=4)
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



    damaged_areas = [a["area"].lower() for a in areas_json.get("damaged_areas", [])]
    if not damaged_areas:
        damaged_areas = ["front end"]
    print(f"   Detected damaged areas: {damaged_areas}")

    # ----------------  Phase 1 – Area-specialist Enterprise Detection ----
    # Prompts are designed with complementary shards - A and B cover different parts
    area_prompt_map = {
        "front end": [PROMPTS_DIR / "detect_front_A.txt", PROMPTS_DIR / "detect_front_B.txt"],
        "front":     [PROMPTS_DIR / "detect_front_A.txt", PROMPTS_DIR / "detect_front_B.txt"],
        "left side":  [PROMPTS_DIR / "detect_side_A.txt"],
        "right side": [PROMPTS_DIR / "detect_side_B.txt"],
        "side":       [PROMPTS_DIR / "detect_side_A.txt", PROMPTS_DIR / "detect_side_B.txt"],
        "rear":       [PROMPTS_DIR / "detect_rear_A.txt", PROMPTS_DIR / "detect_rear_B.txt"],
        "rear end":   [PROMPTS_DIR / "detect_rear_A.txt", PROMPTS_DIR / "detect_rear_B.txt"],
    }    
    
    # Remove duplicate areas to prevent running same prompt combinations twice
    damaged_areas = list(dict.fromkeys(damaged_areas))  # Preserve order, remove duplicates







    def run_area_detection_task(area, prompt_path, temp, imgs_for_call, model):
        """Run a single area detection task with specific temperature"""
        try:
            prompt_text = prompt_path.read_text()
            task_id = f"{area}-{prompt_path.name}-temp{temp}"
            print(f"    Running {task_id}...")
            
            txt = call_openai_vision(prompt_text, imgs_for_call, model, temperature=temp, max_images=4)
            if txt.startswith("```"):
                if "json" in txt.split("\n")[0]:
                    txt = txt.split("\n",1)[1].rsplit("```",1)[0].strip()
                else:
                    txt = txt.split("```",1)[1].rsplit("```",1)[0].strip()
            
            result = json.loads(txt)
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
            for temp in [0.0]:  # Max determinism for consistency
                detection_tasks.append((area, prompt_path, temp, imgs_for_call))
    
    print(f"Phase 1: Running {len(detection_tasks)} area-specialist detection tasks in parallel...")
    
    # Execute all tasks in parallel with optimal thread count
    max_workers = min(8, len(detection_tasks))  # Don't overwhelm OpenAI API
    runs = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {executor.submit(run_area_detection_task, area, prompt_path, temp, imgs, args.model): (area, prompt_path.name, temp)
                         for area, prompt_path, temp, imgs in detection_tasks}
        
        completed_count = 0
        for future in concurrent.futures.as_completed(future_to_task):
            area, prompt_name, temp = future_to_task[future]
            try:
                result = future.result(timeout=30)  # 30 second timeout per task
                if result:  # Only add successful results
                    runs.append(result)
                completed_count += 1
                print(f"Progress: {completed_count}/{len(detection_tasks)} tasks completed")
            except Exception as e:
                print(f"Task {area}-{prompt_name}-{temp} failed: {e}")

    if not runs:
        sys.exit("Enterprise detection failed for all areas")

    detected = union_parts(runs)
# ---------------- vehicle back-fill from quick detector ---------------
    quick_vehicle = areas_json.get("vehicle", {})
    for k in ("make", "model", "year"):
        if detected["vehicle"].get(k, "Unknown") in ("", "Unknown", 0):
            val = quick_vehicle.get(k)
            if val not in (None, "", "Unknown", 0):
                detected["vehicle"][k] = val
    print(f"Detected {len(detected['damaged_parts'])} unique parts after merging")

        # Phase 2 – Describe --------------------------------------------------
    p2_base = PHASE2_PROMPT.read_text()
    p2_prompt = p2_base.replace("<DETECTED_PARTS_JSON>", json.dumps(detected["damaged_parts"]))
    print("Phase 2: describing parts…")
    desc_txt = call_openai_text(p2_prompt, args.model)
    if desc_txt.startswith("```"):
        desc_txt = desc_txt.split("\n",1)[1].rsplit("```",1)[0].strip()
    desc_json = json.loads(desc_txt)
    detected["damaged_parts"] = desc_json["damaged_parts"]

    # Phase 3 – Plan parts -------------------------------------------------
    p3_base = PHASE3_PROMPT.read_text()
    p3_prompt = p3_base.replace("<DETECTED_PARTS_JSON>", json.dumps(detected["damaged_parts"]))
    print("Phase 3: planning repair parts…")
    parts_txt = call_openai_text(p3_prompt, args.model)
    if parts_txt.startswith("```"):
        parts_txt = parts_txt.split("\n",1)[1].rsplit("```",1)[0].strip()
    parts_json = json.loads(parts_txt)
    detected["repair_parts"] = parts_json.get("repair_parts", [])

    # Phase 4 – Summary ----------------------------------------------------
    p4_base = PHASE4_PROMPT.read_text()
    p4_prompt = p4_base.replace("<FULL_REPORT_JSON>", json.dumps(detected))
    print("Phase 4: summarising…")
    summary_txt = call_openai_text(p4_prompt, args.model)
    if summary_txt.startswith("```"):
        summary_txt = summary_txt.split("\n",1)[1].rsplit("```",1)[0].strip()
    detected["summary"] = json.loads(summary_txt)

    # FINAL DUPLICATE CLEANUP - catch any remaining duplicates with fuzzy matching
    final_parts = []
    seen_parts = []  # Use list to enable fuzzy comparison
    
    for part in detected["damaged_parts"]:
        part_name = part.get("name", "").lower().strip()
        location = part.get("location", "").lower().strip()
        
        # Check against all previously seen parts for fuzzy matches
        is_duplicate = False
        for seen_part in seen_parts:
            seen_name = seen_part["name"]
            seen_location = seen_part["location"]
            
            # Enhanced duplicate detection
            if (part_name == seen_name or 
                (part_name in seen_name or seen_name in part_name) and len(part_name) > 3 or
                (location == seen_location and location and 
                 part.get("category") == seen_part["category"] and
                 any(keyword in part_name and keyword in seen_name 
                     for keyword in ["fender", "bumper", "headlight", "grille"]))):
                is_duplicate = True
                print(f"❌ DUPLICATE REMOVED: '{part.get('name', 'Unknown')}' (matches '{seen_part['original_name']}')")
                break
        
        if not is_duplicate:
            final_parts.append(part)
            seen_parts.append({
                "name": part_name,
                "location": location, 
                "category": part.get("category", ""),
                "original_name": part.get("name", "Unknown")
            })
            print(f"✅ Keeping: {part.get('name', 'Unknown')}")
    
    detected["damaged_parts"] = final_parts
    print(f"Final cleanup: {len(final_parts)} unique parts remaining")

    report = detected

    # Write the report to file
    Path(args.out).write_text(json.dumps(report, indent=2))
    print(f"Final report written to {args.out}")

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
