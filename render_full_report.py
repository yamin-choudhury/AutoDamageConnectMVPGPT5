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
.plain-img{display:inline-block;margin:10px;border:1px solid #ccc;box-shadow:0 0 6px rgba(0,0,0,.1)}
.plain-img img{display:block}
.damage-map-wrapper{display:flex;justify-content:center;gap:40px;margin:40px 0}.damage-view{text-align:center;font-size:14px;color:#555}
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
        notes_html = p.get('notes','')
        rows.append(f"<tr><td>{p['name']}</td><td>{p['location']}</td><td class='{severity_class(p['severity'])}'>{p['severity']}</td><td>{p['damage_type']}</td><td>{p['repair_method']}</td><td>{p['image']} #{p['box_id']}</td><td>{desc_html}</td><td>{notes_html}</td></tr>")
    table_html = """
    <div class='table-wrapper'>
    <h2>Damage Overview</h2>
    <table>
        <thead><tr><th>Part</th><th>Location</th><th>Severity</th><th>Damage Type</th><th>Repair Method</th><th>Image Ref</th><th>Description</th><th>Notes</th></tr></thead>
        <tbody>{}</tbody>
    </table></div>""".format("\n".join(rows))

    # Repair parts table
    repair_rows = []
    for rp in report.get('repair_parts', []):
        sub = ', '.join(rp.get('sub_components', []))
        repair_rows.append(f"<tr><td>{rp['category']}</td><td>{rp['name']}</td><td>{'Yes' if rp['oem_only'] else 'No'}</td><td>{sub}</td><td>{rp['labour_hours']}</td><td>{rp['paint_hours']}</td></tr>")
    repair_table_html = ""
    if repair_rows:
        repair_table_html = """
        <div class='table-wrapper'>
        <h2>Parts Required for Repair</h2>
        <table>
            <thead><tr><th>Category</th><th>Part Name</th><th>OEM Only</th><th>Sub-components</th><th>Labour h</th><th>Paint h</th></tr></thead>
            <tbody>{}</tbody>
        </table></div>""".format("\n".join(repair_rows))

    # Plain images for visual reference
    # Map image name -> list of boxes
    img_map: Dict[str,List[dict]] = {}
    for part in report['damaged_parts']:
        img_map.setdefault(part['image'], []).append(part)

    # ---------------- Multi-view damage map ------------------
    views = [
        {"id": "front", "w": 120, "h": 180, "title": "Front"},
        {"id": "left", "w": 120, "h": 180, "title": "Left"},
        {"id": "rear", "w": 120, "h": 180, "title": "Rear"},
        {"id": "right", "w": 120, "h": 180, "title": "Right"},
    ]

    # helper: choose view(s) and approx coords
    def locate(part: dict):
        loc = part.get('location','').lower()
        name = part.get('name','').lower()
        targets = []
        # decide view
        if 'front' in loc or 'bumper' in name and 'rear' not in loc:
            view = 'front'
        elif 'rear' in loc or 'tail' in name:
            view = 'rear'
        elif 'left' in loc or 'lh' in loc:
            view = 'left'
        elif 'right' in loc or 'rh' in loc:
            view = 'right'
        else:
            # default side based on severity count to spread
            view = 'left'
        # choose y by part category
        y_map = {
            'roof':30,'window':60,'windscreen':60,'bonnet':60,'hood':60,'door':90,
            'fender':100,'quarter':120,'bumper':150,'wheel':160
        }
        y = 90
        for k,v in y_map.items():
            if k in name:
                y=v
                break
        # x position: center of each SVG
        x = 60
        return view,x,y

    # build svg dict
    svg_parts = {v['id']:[] for v in views}
    for idx,p in enumerate(report['damaged_parts'],1):
        view,x,y = locate(p)
        color = '#c0392b' if p['severity']=='severe' else ('#f39c12' if p['severity']=='moderate' else '#27ae60')
        svg_parts[view].append(f"<circle cx='{x}' cy='{y}' r='10' fill='{color}' opacity='0.8'/><text x='{x-4}' y='{y+4}' fill='#fff' font-size='9'>{idx}</text>")

    damage_map_views = []
    for v in views:
        inner=''.join(svg_parts[v['id']])
        # simple silhouette paths per view for nicer look
        path_map = {
            'front': "M20 60 Q60 20 100 60 L100 120 Q60 150 20 120 Z",
            'rear':  "M20 60 Q60 20 100 60 L100 120 Q60 150 20 120 Z",
            'left':  "M20 40 L100 40 Q110 60 110 80 L110 120 Q110 140 100 140 L20 140 Z",
            'right': "M20 40 L100 40 Q110 60 110 80 L110 120 Q110 140 100 140 L20 140 Z",
        }
        silhouette = f"<path d='{path_map[v['id']]}' fill='#ecf0f1' stroke='#bdc3c7' stroke-width='3' />"
        damage_map_views.append(
            f"<div class='damage-view'><svg width='{v['w']}' height='{v['h']}' viewBox='0 0 {v['w']} {v['h']}'>{silhouette}{inner}</svg><div>{v['title']}</div></div>")
    damage_map_html = "<h2>Damage Map</h2><div class='damage-map-wrapper'>" + ''.join(damage_map_views) + "</div>"
    # ------------------------------------------------------
    def part_to_coords(loc: str):
        loc = loc.lower()
        x = 100  # center default
        y = 200
        if 'front' in loc:
            y = 60
        elif 'rear' in loc or 'back' in loc:
            y = 340
        if 'left' in loc or 'lh' in loc:
            x = 60
        elif 'right' in loc or 'rh' in loc:
            x = 140
        return x, y

    circles = []

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
        section = f"<div class='plain-img'><img src='{data_uri}' width='{w}' height='{h}'/></div>"
        img_sections.append(section)

    images_html = "<h2>Vehicle Images</h2>" + "".join(img_sections)

    # --- build title without Unknown/blank values ---
    title_parts = [vehicle.get('year',''), vehicle.get('make',''), vehicle.get('model','')]
    title = ' '.join(p for p in title_parts if p and p.lower() != 'unknown').strip() or 'Vehicle'

    # --- assemble final HTML ---
    html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>Vehicle Damage Report</title><style>{CSS}</style></head><body>
    <div class='container'>
    <header><h1>Vehicle Damage Report</h1><h2>{title}</h2><p>Generated {now}</p></header>
    {summary_html}
    {table_html}\n    {repair_table_html}
    {damage_map_html}
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
