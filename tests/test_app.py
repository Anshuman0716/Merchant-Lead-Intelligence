"""Smoke test: every dashboard page renders without an exception (headless, no browser)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app"
DATA = Path(__file__).resolve().parents[1] / "exports" / "leads.parquet"
HOME = str(APP / "Home.py")

pytestmark = pytest.mark.skipif(not DATA.exists(), reason="run the pipeline first")


@pytest.mark.parametrize(
    "page",
    [None, "views/lead_explorer.py", "views/competitor_landscape.py", "views/lead_detail.py"],
)  # fmt: skip
def test_page_renders(page):
    at = AppTest.from_file(HOME, default_timeout=60).run()
    if page:
        at.switch_page(page).run()
    assert not at.exception, at.exception


@pytest.mark.parametrize("domain", ["livpure.com", "lenskart.com", "animaker.com"])
def test_lead_detail_for_crawled_and_blocked_sites(domain):
    at = AppTest.from_file(HOME, default_timeout=60)
    at.query_params["domain"] = domain
    at.run()
    at.switch_page("views/lead_detail.py").run()
    assert not at.exception, at.exception
    assert any(sb.value == domain for sb in at.selectbox)


def test_explorer_filters_narrow_the_list():
    at = AppTest.from_file(HOME, default_timeout=60).run()
    at.switch_page("views/lead_explorer.py").run()
    at.selectbox(key="f_search").set_value("livpure.com").run()
    assert not at.exception, at.exception
    assert at.session_state["_keep_f_search"] == "livpure.com"


def test_call_log_round_trip(tmp_path, monkeypatch):
    import sys

    sys.path.insert(0, str(APP))
    import common

    monkeypatch.setattr(common, "CALL_LOG", tmp_path / "log.csv")
    assert common.read_call_log().empty
    common.append_call_log({"domain": "livpure.com", "outcome": "Meeting booked",
                            "budget_status": "Confirmed"})  # fmt: skip
    common.append_call_log({"domain": "livpure.com", "outcome": "Voicemail"})
    log = common.read_call_log()
    assert len(log) == 2 and log.iloc[0]["budget_status"] == "Confirmed"
    assert common.last_outcomes()["livpure.com"] in {"Meeting booked", "Voicemail"}
