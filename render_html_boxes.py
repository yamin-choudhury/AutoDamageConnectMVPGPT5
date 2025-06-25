#!/usr/bin/env python3
"""Render damage report JSON into an HTML document with inline annotated images.

Usage:
    python render_html_boxes.py report_ai.json copartimages/vehicle1 --out annotated_report.html

This is self-contained and does NOT rely on the external eBayRepairAgent package.
It uses SVG overlays to draw bounding boxes so there is no client-side JS needed.
"""
from __future__ import annotations
import argparse, json, os, base64
from pathlib import Path
from typing import Dict, List
from PIL import Image

def inline_image_base64(img_path: Path, max_px: int = 1000) -> str:
    """Return a base64 data URI for the image, downscaled for HTML weight."""
    img = Image.open(img_path).convert("RGB")
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px))
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"

def build_html(report: Dict, images_dir: Path) -> str:
    # Build mapping image -> list of boxes
    img_map: Dict[str, List[dict]] = {}
    for part in report["damaged_parts"]:
        img_map.setdefault(part["image"], []).append(part)

    sections = []
    for img_name, parts in img_map.items():
        img_path = images_dir / img_name
        if not img_path.exists():
            # Skip missing images
            continue
        data_uri = inline_image_base64(img_path)
        width, height = Image.open(img_path).size
        svg_elems = []
        for p in parts:
            box = p["bbox_px"]
            color = "#e74c3c" if p["severity"] == "severe" else ("#f39c12" if p["severity"] == "moderate" else "#27ae60")
            svg_elems.append(
                f'<rect x="{box["x"]}" y="{box["y"]}" width="{box["w"]}" height="{box["h"]}" fill="none" stroke="{color}" stroke-width="4" />'
            )
            # label
            svg_elems.append(
                f'<text x="{box["x"]+5}" y="{box["y"]+20}" fill="{color}" font-size="20" font-weight="bold">#{p["box_id"]}</text>'
            )
        svg_markup = "".join(svg_elems)
        section = f"""
        <div class=\"annotated\">
            <svg width=\"{width}\" height=\"{height}\" viewBox=\"0 0 {width} {height}\" xmlns='http://www.w3.org/2000/svg' style='position: absolute;'>
                {svg_markup}
            </svg>
            <img src='{data_uri}' width='{width}' height='{height}' />
        </div>"""
        sections.append(section)

    html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>Annotated Damage Images</title>
<style>
body{{font-family:Arial, sans-serif;background:#f5f5f5;margin:0;padding:20px;}}
.annotated{{position:relative;display:inline-block;margin:10px;border:1px solid #ccc;box-shadow:0 0 8px rgba(0,0,0,0.1);}}
.annotated img{{display:block;}}
.annotated svg{{pointer-events:none;}}
</style>
</head><body>
<h1>Annotated Damage Images</h1>
{''.join(sections)}
</body></html>"""
    return html

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path")
    ap.add_argument("images_dir")
    ap.add_argument("--out", default="annotated_report.html")
    args = ap.parse_args()

    report = json.loads(Path(args.json_path).read_text())
    html = build_html(report, Path(args.images_dir))
    out_path = Path(args.out)
    out_path.write_text(html, encoding="utf-8")
    print(f"HTML with annotations written to {out_path}")

if __name__ == "__main__":
    main()
