"""Save dashboard screenshots for the README into docs/screenshots/.

    uv run streamlit run app/Home.py --server.port 8510      # in one terminal
    uv run --with playwright python scripts/screenshots.py   # in another
(first time only: uv run --with playwright playwright install chromium)
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8510"
OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
PAGES = {
    "overview.png": "/",
    "lead_explorer.png": "/Lead_Explorer",
    "competitor_landscape.png": "/Competitor_Landscape",
    "lead_detail.png": "/Lead_Detail?domain=livpure.com",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)
        for name, path in PAGES.items():
            page.goto(BASE + path, wait_until="networkidle")
            page.wait_for_selector('.hero, .ph, .lead-name', timeout=30_000)
            page.wait_for_timeout(2500)  # let Plotly charts finish drawing
            page.screenshot(path=str(OUT / name), full_page=True)
            print("saved", name)
        browser.close()


if __name__ == "__main__":
    main()
