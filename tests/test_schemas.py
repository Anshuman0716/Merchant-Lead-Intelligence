"""Each stage's output passes its Pandera schema, and the schemas reject bad data."""

from datetime import date, datetime

import pandera.errors as pa_errors
import polars as pl
import pytest

from leadintel.clean import build_companies
from leadintel.detect import detect_domain, to_frame
from leadintel.htmlparse import parse_page
from leadintel.ingest import load_seeds
from leadintel.schemas import Companies, LeadScores, RawCompanies, Signals
from leadintel.score import build_lead
from leadintel.settings import load_config


def test_seed_csvs_pass_raw_schema():
    df = load_seeds()
    assert df.height >= 350
    RawCompanies.validate(df)
    assert set(df["vertical"].unique()) == {"d2c", "edtech", "saas"}


def test_companies_stage_output_passes_schema():
    raw = load_seeds().head(20)
    out = build_companies(raw, reach={})  # offline: no reachability results
    Companies.validate(out)
    assert out["domain"].is_unique().all()


def test_signals_stage_output_passes_schema():
    html = '<script src="https://cdn.shopify.com/x.js"></script><p>Cash on delivery</p>'
    rows = [
        detect_domain(
            "a.in", {"home": parse_page(html, "https://a.in/")}, load_config("fingerprints")
        ),
        detect_domain("b.in", {}, load_config("fingerprints")),
    ]
    df = to_frame(rows)
    Signals.validate(df)
    assert df.filter(pl.col("domain") == "a.in")["platform"][0] == "shopify"


def test_lead_scores_output_passes_schema():
    row = {
        "domain": "a.in", "name": "A", "vertical": "d2c", "funding_stage": "A",
        "last_funding_date": date(2026, 5, 1), "platform": "shopify", "gateways_detected": [],
        "gateway_confidence": None, "checkout_layer": "gokwik", "has_subscription": False,
        "has_international": False, "has_cod": True, "has_emi": False, "has_android_app": False,
        "has_ios_app": False, "has_pricing_page": False, "contact_email": None,
        "pages_crawled": 3, "evidence": "{}",
    }  # fmt: skip
    lead = build_lead(row, load_config("icp"), date(2026, 10, 31), datetime(2026, 10, 31))
    df = pl.DataFrame(
        [lead],
        schema_overrides={"reasons": pl.List(pl.Utf8), "suggested_products": pl.List(pl.Utf8)},
    )
    LeadScores.validate(df.select(list(LeadScores.to_schema().columns)))


@pytest.mark.parametrize(
    "bad",
    [{"score": 120}, {"tier": "D"}, {"icp": "unknown_icp"}, {"opener": ""}],
)
def test_lead_scores_schema_rejects_bad_values(bad):
    good = {
        "domain": "a.in", "icp": "d2c_growth", "score": 50, "tier": "A", "reasons": ["x"],
        "bant_budget": "b", "bant_authority": "a", "bant_need": "n", "bant_timeline": "t",
        "suggested_products": ["Payment Gateway"], "opener": "Hi A?", "data_coverage": "website",
        "scored_at": datetime(2026, 10, 31),
    }  # fmt: skip
    df = pl.DataFrame([{**good, **bad}])
    with pytest.raises((pa_errors.SchemaError, pa_errors.SchemaErrors)):
        LeadScores.validate(df)
