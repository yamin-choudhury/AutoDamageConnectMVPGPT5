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
from PIL import Image
from tqdm import tqdm
from copy import deepcopy


PHASE1_PROMPT = Path(__file__).parent / "prompts/detect_parts_prompt.txt"
PHASE2_PROMPT = Path(__file__).parent / "prompts/describe_parts_prompt.txt"
PHASE3_PROMPT = Path(__file__).parent / "prompts/plan_parts_prompt.txt"
PHASE4_PROMPT = Path(__file__).parent / "prompts/summary_prompt.txt"


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
        max_tokens=4096,
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


def call_openai_text(prompt: str, model: str = "gpt-4o", temperature: float = 0.2) -> str:
    resp = openai.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": prompt}],
        max_tokens=4096,
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


# ----------------------- Ensemble utilities ---------------------------

def iou(box_a: dict, box_b: dict) -> float:
    xa1, ya1, wa, ha = box_a.values()
    xa2, ya2 = xa1 + wa, ya1 + ha
    xb1, yb1, wb, hb = box_b.values()
    xb2, yb2 = xb1 + wb, yb1 + hb
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
    for run in runs[1:]:
        for cand in run["damaged_parts"]:
            duplicate = False
            for base in merged["damaged_parts"]:
                if cand["image"] == base["image"] and iou(cand["bbox_px"], base["bbox_px"]) > 0.3:
                    duplicate = True
                    break
            if not duplicate:
                merged["damaged_parts"].append(cand)
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

        # Phase 1 – Detection (two-pass ensemble) ---------------------------
    p1_prompt = PHASE1_PROMPT.read_text()
    print("Phase 1: detecting parts (2-pass ensemble)…")
    runs = []
    for temp in (0.2, 0.6):
        txt = call_openai_vision(p1_prompt, images, args.model, temperature=temp)
        if txt.startswith("```"):
            txt = txt.split("\n",1)[1].rsplit("```",1)[0].strip()
        try:
            runs.append(json.loads(txt))
        except json.JSONDecodeError:
            print("Warning: JSON parse failure in a pass, skipping")
    if not runs:
        sys.exit("All detection passes failed")
    detected = union_parts(runs)
    print(f"Detected {len(detected['damaged_parts'])} unique parts after merge")

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
