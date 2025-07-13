#!/usr/bin/env python3
"""Two-phase damage report generator: Detection → Enrichment.

Usage:
 python generate_damage_report_staged.py --images_dir copartimages/vehicle1 \
                                        --out report_full.json
"""
from __future__ import annotations
import argparse, base64, json, os, sys
from pathlib import Path
from typing import List

import openai
from dotenv import load_dotenv
from PIL import Image, ImageOps
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
PHASE2_PROMPT = PROMPTS_DIR / "describe_parts_prompt.txt"
PHASE3_PROMPT = PROMPTS_DIR / "plan_parts_prompt.txt"
PHASE4_PROMPT = PROMPTS_DIR / "summary_prompt.txt"


# ----------------------- YOLO integration disabled -------------------
# placeholder no-op

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

def encode_image_b64(p: Path, max_px: int = 2000) -> str:
    img = Image.open(p).convert("RGB")
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px))
    with p.open("rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


def call_openai_vision(prompt: str, images: List[Path], model: str = "gpt-4o", temperature: float = 0.2) -> str:
    user_parts = [{"type": "text", "text": "Please analyse all images and reply with JSON only."}]
    
    for img in images:
        user_parts.append({"type": "image_url", "image_url": {"url": encode_image_b64(img)}})

    resp = openai.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_parts}],
        max_tokens=6144,
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


def call_openai_text(prompt: str, model: str = "gpt-4o", temperature: float = 0.2) -> str:
    resp = openai.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": prompt}],
        max_tokens=6144,
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


# ----------------------- Image cropping utilities --------------------

def make_crops(area: str, images: List[Path], areas_json: dict, max_px: int = 1200) -> List[Path]:
    """Return a list of Path objects: [full_frame, roi_crop] (if bbox present).
    Creates temporary JPEG crops in /tmp and returns their paths.
    """
    out: List[Path] = []
    tmp_dir = Path("/tmp/damage_crops")
    tmp_dir.mkdir(exist_ok=True)
    # Use first 3 images only to keep token count reasonable
    base_imgs = images[:3]
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
    merged = deepcopy(runs[0])
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
        for cand in run["damaged_parts"]:
            duplicate = False
            for i, base in enumerate(merged["damaged_parts"]):
                # Normalize part names for comparison
                cand_name = cand.get("name", "").lower().strip()
                base_name = base.get("name", "").lower().strip()
                
                # Potential duplicate if same part name AND (same image OR IoU≥0.6)
                same_image = cand.get("image") == base.get("image")
                high_iou = False
                try:
                    high_iou = iou(cand.get("bbox_px", []), base.get("bbox_px", [])) >= 0.3
                except Exception:
                    pass
                if cand_name == base_name and (same_image or high_iou):
                    
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

        # ----------------  Phase 0 – Quick Area Detection  -----------------
    quick_prompt = PHASE0_QUICK_PROMPT.read_text()
    print("Phase 0: Quick damaged-area detection (per image) …")
    quick_runs = []
    for idx, img in enumerate(images, 1):
        try:
            quick_txt = call_openai_vision(quick_prompt, [img], args.model, temperature=0.3)
            if quick_txt.startswith("```"):
                quick_txt = quick_txt.split("```",1)[1].rsplit("```",1)[0].strip()
            quick_runs.append(json.loads(quick_txt))
            print(f"   Image {idx}: success")
        except Exception as e:
            print(f"   Image {idx}: quick detection failed – {e}")
    if not quick_runs:
        print("   Quick detection failed for all images – running generic area detector …")
        try:
            generic_txt = call_openai_vision(GENERIC_AREAS_PROMPT.read_text(), images, args.model, temperature=0.3)
            if generic_txt.startswith("```"):
                generic_txt = generic_txt.split("```",1)[1].rsplit("```",1)[0].strip()
            generic_json = json.loads(generic_txt)
            areas_json = {"vehicle": {"make": "Unknown", "model": "Unknown", "year": 0},
                          "damaged_areas": generic_json.get("damaged_areas", [])}
            if not areas_json["damaged_areas"]:
                print("   Generic detector found no damaged areas – aborting with clear error")
                sys.exit("Unable to determine damaged areas from images")
        except Exception as e:
            sys.exit(f"Generic area detection failed: {e}")
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
            damaged_areas_all.extend(run.get("damaged_areas", []))
        areas_json = {"vehicle": vehicle, "damaged_areas": damaged_areas_all}

    damaged_areas = [a["area"].lower() for a in areas_json.get("damaged_areas", [])]
    if not damaged_areas:
        damaged_areas = ["front end"]
    print(f"   Detected damaged areas: {damaged_areas}")

        # ----------------  Phase 1 – Area-specialist Enterprise Detection ----
    area_prompt_map = {
        "front end": [PROMPTS_DIR / "detect_front_A.txt", PROMPTS_DIR / "detect_front_B.txt"],
        "front":     [PROMPTS_DIR / "detect_front_A.txt", PROMPTS_DIR / "detect_front_B.txt"],
        "left side":  [PROMPTS_DIR / "detect_side_A.txt"],
        "right side": [PROMPTS_DIR / "detect_side_B.txt"],
        "side":       [PROMPTS_DIR / "detect_side_A.txt", PROMPTS_DIR / "detect_side_B.txt"],
        "rear":       [PROMPTS_DIR / "detect_rear_A.txt", PROMPTS_DIR / "detect_rear_B.txt"],
        "rear end":   [PROMPTS_DIR / "detect_rear_A.txt", PROMPTS_DIR / "detect_rear_B.txt"],
    }







    runs = []
    for area in damaged_areas:
        prompt_paths = area_prompt_map.get(area, [PHASE1_FRONT_ENTERPRISE_PROMPT])
        for prompt_path in prompt_paths:
            prompt_text = prompt_path.read_text()
            print(f"Phase 1: {area} assessment with {prompt_path.name} …")
            imgs_for_call = make_crops(area, images, areas_json)
            temperatures = [0.1, 0.4, 0.8]
            for i, temp in enumerate(temperatures, 1):
                print(f"    Pass {i}/3 (temp={temp}) …")
                txt = call_openai_vision(prompt_text, imgs_for_call, args.model, temperature=temp)
            if txt.startswith("```"):
                if "json" in txt.split("\n")[0]:
                    txt = txt.split("\n",1)[1].rsplit("```",1)[0].strip()
                else:
                    txt = txt.split("```",1)[1].rsplit("```",1)[0].strip()
            try:
                result = json.loads(txt)
                combined = {
                    "vehicle": result.get("vehicle", {"make": "Unknown", "model": "Unknown", "year": 0}),
                    "damaged_parts": result.get("damaged_parts", [])
                }
                runs.append(combined)
                print(f"      → {len(combined['damaged_parts'])} parts")
            except Exception as e:
                print("      JSON parse failed, skipping this pass")

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
    runs = []
    
    # 3-pass ensemble with different temperatures for maximum coverage
    temperatures = [0.1, 0.4, 0.8]  # Conservative, balanced, creative
    for i, temp in enumerate(temperatures, 1):
        print(f"  Pass {i}/3 (temp={temp}): Chain-of-thought analysis...")
        txt = call_openai_vision(PHASE1_FRONT_ENTERPRISE_PROMPT.read_text(), images, args.model, temperature=temp)
        
        # Clean up markdown formatting
        if txt.startswith("```"):
            if "json" in txt.split("\n")[0]:
                txt = txt.split("\n",1)[1].rsplit("```",1)[0].strip()
            else:
                txt = txt.split("```",1)[1].rsplit("```",1)[0].strip()
        
        try:
            result = json.loads(txt)
            # Extract vehicle info and damaged parts
            combined = {
                "vehicle": result.get("vehicle", {"make": "Unknown", "model": "Unknown", "year": 0}),
                "damaged_parts": result.get("damaged_parts", [])
            }
            runs.append(combined)
            parts_count = len(result.get("damaged_parts", []))
            print(f"    Found {parts_count} damaged parts")
            
            # Log reasoning process for debugging
            if "reasoning_process" in result:
                print(f"    Reasoning: {result['reasoning_process'][:100]}...")
                
        except json.JSONDecodeError as e:
            print(f"    Warning: JSON parse failure in pass {i}, skipping")
            print(f"    Raw response preview: {txt[:200]}...")
    if not runs:
        sys.exit("All comprehensive detection passes failed")
    # (removed line as now above)

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

    report = detected

    Path(args.out).write_text(json.dumps(report, indent=2))
    print(f"Final report written to {args.out}")

if __name__ == "__main__":
    main()
