"""Export files: HubSpot CSV importable, Tier A list consistent, Parquet has app columns."""

from pathlib import Path

import polars as pl
import pytest

from leadintel.export import HUBSPOT_INDUSTRY, hubspot_frame, tier_a_frame

LEADS = Path(__file__).resolve().parents[1] / "exports" / "leads.parquet"
pytestmark = pytest.mark.skipif(not LEADS.exists(), reason="run the pipeline first")

REQUIRED_HUBSPOT = [
    "Company name", "Company Domain Name", "Industry", "City", "Lead tier", "ICP score",
    "Current gateway", "Suggested products", "Opener",
]  # fmt: skip


@pytest.fixture(scope="module")
def leads() -> pl.DataFrame:
    return pl.read_parquet(LEADS)


def test_hubspot_csv_has_required_columns_and_no_empty_names(leads):
    hs = hubspot_frame(leads)
    assert set(REQUIRED_HUBSPOT) <= set(hs.columns)
    assert hs["Company name"].null_count() == 0
    assert (hs["Company name"].str.strip_chars() != "").all()
    assert hs["Company Domain Name"].is_unique().all()


def test_hubspot_industry_uses_hubspot_labels(leads):
    assert set(hubspot_frame(leads)["Industry"].unique()) <= set(HUBSPOT_INDUSTRY.values())


def test_hubspot_lists_are_flattened_to_text(leads):
    hs = hubspot_frame(leads)
    assert hs.schema["Suggested products"] == pl.Utf8
    assert hs.schema["Current gateway"] == pl.Utf8


def test_tier_a_export_only_tier_a(leads):
    a = tier_a_frame(leads)
    assert a.height == leads.filter(pl.col("tier") == "A").height
    assert (a["score"] >= 0).all() and a["opener"].null_count() == 0


def test_parquet_has_columns_the_app_reads(leads):
    needed = {
        "domain", "name", "vertical_label", "tier", "score", "reasons", "opener",
        "suggested_products", "gateway_names", "checkout_layer_name", "platform_label",
        "evidence", "data_coverage", "bant_need", "contact_email",
    }  # fmt: skip
    assert needed <= set(leads.columns)
