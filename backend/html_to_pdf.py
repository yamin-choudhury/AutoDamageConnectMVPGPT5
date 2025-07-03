#!/usr/bin/env python3
"""Convert an HTML file to PDF using Playwright/Chromium.

Usage:
    python html_to_pdf.py input.html output.pdf
The script makes sure Playwright and the Chromium browser are available at runtime
(even inside minimal containers) by installing them on-the-fly if missing.
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

ASYNC_TIMEOUT_MS = 30_000  # 30 s


async def ensure_playwright_installed() -> None:
    """Install Playwright + Chromium if they are not already present."""
    try:
        import playwright  # noqa: F401  # type: ignore
    except ModuleNotFoundError:
        print("Playwright not found – installing via pip…", file=sys.stderr)
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)

    # Whether playwright was pre-installed or we just installed it, ensure Chromium is present
    print("Ensuring Chromium browser is installed…", file=sys.stderr)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


async def html_to_pdf(in_path: Path, out_path: Path) -> None:
    """Render *in_path* HTML to *out_path* PDF."""
    from playwright.async_api import async_playwright  # type: ignore

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(in_path.as_uri(), wait_until="networkidle", timeout=ASYNC_TIMEOUT_MS)
        await page.pdf(path=str(out_path), format="A4", print_background=True)
        await browser.close()


async def _main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python html_to_pdf.py input.html output.pdf", file=sys.stderr)
        sys.exit(1)

    html_file = Path(sys.argv[1]).expanduser().resolve()
    pdf_file = Path(sys.argv[2]).expanduser().resolve()
    if not html_file.exists():
        sys.exit(f"Input file {html_file} not found")

    await ensure_playwright_installed()
    await html_to_pdf(html_file, pdf_file)
    print(f"PDF written to {pdf_file}")


if __name__ == "__main__":
    asyncio.run(_main())
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



def usage():
    print("Usage: python html_to_pdf.py <input.html> <output.pdf>")
    sys.exit(1)


aSYNC_TIMEOUT = 30000  # 30 s

async def run(in_path: Path, out_path: Path):
    # Import playwright lazily so we can install it on the fly if missing
    try:
        from playwright.async_api import async_playwright, Error as PlaywrightError  # type: ignore
    except ModuleNotFoundError:
        print("Playwright not installed – installing via pip…", file=sys.stderr)
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
        from playwright.async_api import async_playwright, Error as PlaywrightError  # type: ignore

        try:
        import subprocess, os
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
    except PlaywrightError:
        # Likely chromium not installed in the image – install and retry once
        print("Chromium not found – installing with 'playwright install chromium'…", file=sys.stderr)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        # recursion single retry
        await run(in_path, out_path)
        return
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
