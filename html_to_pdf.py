#!/usr/bin/env python3
"""Convert an HTML report to PDF using Playwright/Chromium.

Usage:
  python html_to_pdf.py full_report.html out.pdf

Requirements:
  pip install playwright && playwright install chromium

Playwright is already used elsewhere in the project so the runtime
should have it available. The script launches headless Chromium,
opens the local HTML file, waits for network-idle, and prints to PDF
(A4 portrait with 20 mm margins).
"""
from __future__ import annotations
import sys, asyncio
from pathlib import Path
try:
    from playwright.async_api import async_playwright  # type: ignore
except ModuleNotFoundError:
    import subprocess, sys as _sys
    print("Playwright missing – installing…", file=_sys.stderr)
    subprocess.run([_sys.executable, "-m", "pip", "install", "playwright"], check=True)
    subprocess.run([_sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    from playwright.async_api import async_playwright  # type: ignore


def usage():
    print("Usage: python html_to_pdf.py <input.html> <output.pdf>")
    sys.exit(1)


aSYNC_TIMEOUT = 30000  # 30 s

async def run(in_path: Path, out_path: Path):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(in_path.as_uri(), wait_until="networkidle", timeout=aSYNC_TIMEOUT)
        await page.pdf(
            path=str(out_path),
            format="A4",
            margin={"top": "20mm", "bottom": "20mm", "left": "15mm", "right": "15mm"},
            print_background=True,
        )
        await browser.close()
        print(f"PDF written to {out_path}")


def main():
    if len(sys.argv) != 3:
        usage()
    in_file = Path(sys.argv[1]).expanduser().resolve()
    out_file = Path(sys.argv[2]).expanduser().resolve()
    if not in_file.exists():
        sys.exit(f"Input file {in_file} not found")
    asyncio.run(run(in_file, out_file))


if __name__ == "__main__":
    main()
