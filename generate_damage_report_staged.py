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

PHASE1_PROMPT = Path(__file__).parent / "prompts/detect_parts_prompt.txt"
PHASE2_PROMPT = Path(__file__).parent / "prompts/enrich_report_prompt.txt"


def encode_image_b64(p: Path, max_px: int = 2000) -> str:
    img = Image.open(p).convert("RGB")
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px))
    with p.open("rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


def call_openai_vision(prompt: str, images: List[Path], model: str = "gpt-4o") -> str:
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


def call_openai_text(prompt: str, model: str = "gpt-4o") -> str:
    resp = openai.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": prompt}],
        max_tokens=4096,
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


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

    # Phase 1 – Detection --------------------------------------------------
    p1_prompt = PHASE1_PROMPT.read_text()
    print("Phase 1: detecting parts…")
    detect_json_txt = call_openai_vision(p1_prompt, images, args.model)
    if detect_json_txt.startswith("```"):
        detect_json_txt = detect_json_txt.split("\n",1)[1].rsplit("```",1)[0].strip()
    detected = json.loads(detect_json_txt)
    print(f"Detected {len(detected['damaged_parts'])} parts")

    # Phase 2 – Enrichment --------------------------------------------------
    p2_base = PHASE2_PROMPT.read_text()
    p2_prompt = p2_base.replace("<DETECTED_PARTS_JSON>", json.dumps(detected))
    print("Phase 2: enriching report…")
    full_json_txt = call_openai_text(p2_prompt, args.model)
    if full_json_txt.startswith("```"):
        full_json_txt = full_json_txt.split("\n",1)[1].rsplit("```",1)[0].strip()
    report = json.loads(full_json_txt)

    Path(args.out).write_text(json.dumps(report, indent=2))
    print(f"Final report written to {args.out}")

if __name__ == "__main__":
    main()
