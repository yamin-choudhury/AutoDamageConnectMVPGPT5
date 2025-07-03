#!/usr/bin/env python3
"""
Convert an HTML file to PDF using Playwright/Chromium.

Usage:
    python html_to_pdf.py input.html output.pdf

The script ensures Playwright and its Chromium browser are available even
inside minimal containers by installing them on-the-fly if missing.
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

ASYNC_TIMEOUT_MS = 30_000  # 30 s


def _run(cmd: list[str]) -> None:
    """Run *cmd* and raise if it fails."""
    subprocess.run(cmd, check=True)


async def ensure_playwright() -> None:
    """Guarantee Playwright and Chromium are installed."""
    try:
        import playwright  # noqa: F401  # type: ignore
    except ModuleNotFoundError:
        print("Playwright missing – installing…", file=sys.stderr)
        _run([sys.executable, "-m", "pip", "install", "playwright"])

    # Idempotent: does nothing if Chromium already present
    _run([sys.executable, "-m", "playwright", "install", "chromium"])


async def render_pdf(html: Path, pdf: Path) -> None:
    """Render *html* file to *pdf*."""
    from playwright.async_api import async_playwright  # type: ignore

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(html.as_uri(), wait_until="networkidle", timeout=ASYNC_TIMEOUT_MS)
        await page.pdf(path=str(pdf), format="A4", print_background=True)
        await browser.close()


async def _main() -> None:
    if len(sys.argv) != 3:
        sys.exit("Usage: python html_to_pdf.py input.html output.pdf")

    html_path = Path(sys.argv[1]).resolve()
    pdf_path = Path(sys.argv[2]).resolve()
    if not html_path.exists():
        sys.exit(f"{html_path} not found")

    await ensure_playwright()
    await render_pdf(html_path, pdf_path)
    print(f"PDF written to {pdf_path}")


if __name__ == "__main__":
    asyncio.run(_main())
