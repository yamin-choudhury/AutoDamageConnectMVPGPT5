#!/usr/bin/env python3
"""Generate an industry-standard vehicle damage report using GPT-4o Vision.

Prerequisites
-------------
1. `OPENAI_API_KEY` must be set in the environment or stored in `~/.config/openai`.
2. Requires `openai>=1.14.0`, `tqdm`, `pillow`.
   Install:  pip install openai tqdm pillow

Usage
-----
python generate_damage_report.py --images_dir copartimages/vehicle1 \
                                --prompt_file ../../eBayRepairAgent/prompts/damage_report_prompt.txt \
                                --parts_csv   ../../eBayRepairAgent/prompts/comprehensive_parts_list.csv \
                                --out report_vehicle1.json
"""
import argparse
import base64
import json
import os
import textwrap
from pathlib import Path

import openai
from dotenv import load_dotenv  # type: ignore

from tqdm import tqdm
from PIL import Image

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def load_prompt(prompt_path: Path) -> str:
    """Return the base prompt string."""
    return prompt_path.read_text(encoding="utf-8")


def compress_parts_csv(csv_path: Path) -> str:
    """Compress the CSV into category: item1, item2 lines (<2 k tokens)."""
    parts_by_cat = {}
    with csv_path.open() as f:
        for line in f:
            if line.strip() == "" or line.startswith("Category"):
                continue
            cat, part = line.strip().split(",", 1)
            parts_by_cat.setdefault(cat, []).append(part)
    lines = []
    for cat, items in parts_by_cat.items():
        joined = ", ".join(items)
        lines.append(f"{cat}: {joined}")
    return "\n".join(lines)


def encode_image_b64(img_path: Path, max_px: int = 2000) -> str:
    """Load, optionally downscale, and base64-encode image."""
    img = Image.open(img_path)
    img = img.convert("RGB")
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px))
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


# ---------------------------------------------------------------------------
# Main call
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Generate damage report with GPT-4o Vision")
    ap.add_argument("--model", default="gpt-4o", help="OpenAI model name (e.g., gpt-4o)")
    ap.add_argument("--images_dir", required=True, help="Directory with JPEG/PNG images")
    ap.add_argument("--prompt_file", required=True, help="Path to damage_report_prompt.txt")
    ap.add_argument("--parts_csv", required=True, help="Path to comprehensive_parts_list.csv")
    ap.add_argument("--out", default="damage_report.json", help="Where to write JSON result")
    args = ap.parse_args()

    images = sorted([p for p in Path(args.images_dir).glob("*.jp*g")])
    if not images:
        raise SystemExit("No images found in directory")

    # Assemble messages ------------------------------------------------------
    base_prompt = load_prompt(Path(args.prompt_file))
    parts_block = compress_parts_csv(Path(args.parts_csv))

    system_msg = {
        "role": "system",
        "content": base_prompt + "\n\n### SECTION 3b – AUTHORITATIVE PART NAMES\n" + parts_block,
    }

    user_contents = [
        {"type": "text", "text": "Please analyse all images and output the JSON report as instructed."},
    ]
    for img in tqdm(images, desc="Encoding images"):
        user_contents.append({
            "type": "image_url",
            "image_url": {"url": encode_image_b64(img)}
        })

    user_msg = {"role": "user", "content": user_contents}

    # Call OpenAI ------------------------------------------------------------
    print("Calling OpenAI … (this may take ~30 s)")
    response = openai.chat.completions.create(
        model=args.model,
        messages=[system_msg, user_msg],
        max_tokens=4096,
        temperature=0.2,
    )

    content = response.choices[0].message.content.strip()

    # Remove Markdown code fences if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1]  # drop first line ```json or ```
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

    # Validate JSON ----------------------------------------------------------
    try:
        report = json.loads(content)
    except json.JSONDecodeError as exc:
        print("Model returned invalid JSON; saving raw output for inspection.")
        Path(args.out).with_suffix(".txt").write_text(content, encoding="utf-8")
        raise SystemExit(exc)

    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    load_dotenv()
    main()
