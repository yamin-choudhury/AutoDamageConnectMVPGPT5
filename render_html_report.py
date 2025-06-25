#!/usr/bin/env python3
"""Render an existing damage_report JSON to a nice HTML file using
   ebay_repair_agent.html_report_generator.HTMLReportGenerator.

Usage:
    python render_html_report.py report_vehicle1.json --out vehicle1.html
"""
import argparse
import sys, os
# ensure eBayRepairAgent package is discoverable
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "eBayRepairAgent"))
sys.path.insert(0, project_root)
import json
from pathlib import Path
from ebay_repair_agent.html_report_generator import HTMLReportGenerator

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path", help="Path to damage report JSON")
    ap.add_argument("--out", help="HTML output path")
    args = ap.parse_args()

    data = json.loads(Path(args.json_path).read_text())
    generator = HTMLReportGenerator()
    out_path = generator.generate_report(data, args.out)
    print(f"HTML written to {out_path}")

if __name__ == "__main__":
    main()
