#!/usr/bin/env python3
"""Generate a polished, standalone HTML report that includes:
 • Cover header
 • Summary metrics
 • Damage overview table
 • Annotated images with bounding boxes

Usage:
    python render_full_report.py report_ai.json copartimages/vehicle1 --out full_report.html
"""
from __future__ import annotations
import argparse, json, base64
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from PIL import Image

CSS = """
body{font-family:Arial,sans-serif;background:#f4f6f8;margin:0;padding:0;color:#333}
.container{max-width:1100px;margin:40px auto;background:#fff;box-shadow:0 4px 15px rgba(0,0,0,.08);padding:40px}
header{text-align:center;margin-bottom:40px}
header h1{margin:0;color:#2c3e50}
header h2{margin:10px 0 0;color:#555;font-weight:normal}
summary-box{display:block}
.summary{background:#f8f9fa;border-left:5px solid #2c3e50;padding:20px;margin-bottom:40px}
.summary p{margin:5px 0}
.table-wrapper{overflow-x:auto;margin-bottom:40px}
table{width:100%;border-collapse:collapse}
th,td{border:1px solid #ddd;padding:8px;text-align:left}
th{background:#2c3e50;color:#fff}
.severity-minor{color:#27ae60}
.severity-moderate{color:#f39c12}
.severity-severe{color:#c0392b;font-weight:bold}
.annotated{position:relative;display:inline-block;margin:10px;border:1px solid #ccc;box-shadow:0 0 6px rgba(0,0,0,.1)}
.annotated img{display:block}
.annotated svg{position:absolute;top:0;left:0;pointer-events:none}
footer{text-align:center;margin-top:60px;font-size:14px;color:#777}
"""

def inline_image(img_path: Path, max_px: int = 1000) -> (str, int, int):
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    if max(w, h) > max_px:
        img.thumbnail((max_px, max_px))
        w, h = img.size
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}", w, h

def severity_class(sev: str) -> str:
    return {
        "minor": "severity-minor",
        "moderate": "severity-moderate",
        "severe": "severity-severe",
    }.get(sev, "")

def build_html(report: Dict, images_dir: Path) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    vehicle = report.get("vehicle", {})

    # Summary metrics
    summary_html = f"""
    <div class='summary'>
        <p><strong>Overall Severity:</strong> {report['summary'].get('overall_severity','Unknown')}</p>
        <p><strong>Repair Complexity:</strong> {report['summary'].get('repair_complexity','Unknown')}</p>
        <p><strong>Damaged Parts:</strong> {len(report['damaged_parts'])}</p>
        <p><strong>Total Estimated Hours:</strong> {report['summary'].get('total_estimated_hours','-')}</p>
    </div>"""

    # Damage overview table
    rows = []
    for p in report['damaged_parts']:
        desc_html = p.get('description', '')
        rows.append(f"<tr><td>{p['name']}</td><td>{p['location']}</td><td class='{severity_class(p['severity'])}'>{p['severity']}</td><td>{p['damage_type']}</td><td>{p['image']} #{p['box_id']}</td><td>{desc_html}</td></tr>")
    table_html = """
    <div class='table-wrapper'>
    <h2>Damage Overview</h2>
    <table>
        <thead><tr><th>Part</th><th>Location</th><th>Severity</th><th>Damage Type</th><th>Image Ref</th><th>Description</th></tr></thead>
        <tbody>{}</tbody>
    </table></div>""".format("\n".join(rows))

    # Annotated images
    # Map image name -> list of boxes
    img_map: Dict[str,List[dict]] = {}
    for part in report['damaged_parts']:
        img_map.setdefault(part['image'], []).append(part)

    img_sections = []
    for img_name, parts in img_map.items():
        path = images_dir / img_name
        if not path.exists():
            # fallback: map imageX.jpg (1-indexed) to sorted file list
            if img_name.startswith("image") and img_name.endswith(".jpg"):
                try:
                    idx = int(img_name[5:-4]) - 1  # image3.jpg -> 2
                    all_imgs = sorted(p.name for p in images_dir.glob('*.jp*'))
                    if 0 <= idx < len(all_imgs):
                        path = images_dir / all_imgs[idx]
                except ValueError:
                    pass
            if not path.exists():
                continue
        data_uri, w, h = inline_image(path)
        svg_rects = []
        for p in parts:
            box = p['bbox_px']
            color = '#c0392b' if p['severity']=='severe' else ('#f39c12' if p['severity']=='moderate' else '#27ae60')
            svg_rects.append(f"<rect x='{box['x']}' y='{box['y']}' width='{box['w']}' height='{box['h']}' fill='none' stroke='{color}' stroke-width='4' />")
            svg_rects.append(f"<text x='{box['x']+5}' y='{box['y']+20}' fill='{color}' font-size='20' font-weight='bold'>#{p['box_id']}</text>")
        svg_markup = "".join(svg_rects)
        section = f"<div class='annotated'><svg width='{w}' height='{h}' viewBox='0 0 {w} {h}'>{svg_markup}</svg><img src='{data_uri}' width='{w}' height='{h}'/></div>"
        img_sections.append(section)
    images_html = "<h2>Annotated Images</h2>" + "".join(img_sections)

    html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>Vehicle Damage Report</title><style>{CSS}</style></head><body>
    <div class='container'>
    <header><h1>Vehicle Damage Report</h1><h2>{vehicle.get('make','')} {vehicle.get('model','')}</h2><p>Generated {now}</p></header>
    {summary_html}
    {table_html}
    {images_html}
    <footer>© 2025 AutoDamagePro – AI-generated report. Human verification required.</footer>
    </div></body></html>"""
    return html

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('json_path')
    ap.add_argument('images_dir')
    ap.add_argument('--out', default='full_report.html')
    args = ap.parse_args()
    report = json.loads(Path(args.json_path).read_text())
    html = build_html(report, Path(args.images_dir))
    Path(args.out).write_text(html, encoding='utf-8')
    print(f'Full report written to {args.out}')

if __name__ == '__main__':
    main()
