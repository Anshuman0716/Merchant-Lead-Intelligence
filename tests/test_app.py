"""Smoke test: every dashboard page renders without an exception (headless, no browser)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app"
DATA = Path(__file__).resolve().parents[1] / "exports" / "leads.parquet"

pytestmark = pytest.mark.skipif(not DATA.exists(), reason="run the pipeline first")


@pytest.mark.parametrize(
    "page",
    ["Home.py", "pages/1_Lead_Explorer.py", "pages/2_Competitor_Landscape.py",
     "pages/3_Lead_Detail.py"],
)  # fmt: skip
def test_page_renders(page):
    at = AppTest.from_file(str(APP / page), default_timeout=60).run()
    assert not at.exception, at.exception


@pytest.mark.parametrize("domain", ["livpure.com", "lenskart.com", "animaker.com"])
def test_lead_detail_for_crawled_and_blocked_sites(domain):
    at = AppTest.from_file(str(APP / "pages/3_Lead_Detail.py"), default_timeout=60)
    at.query_params["domain"] = domain
    at.run()
    assert not at.exception, at.exception
    assert domain in at.selectbox[0].value
