import json
from datetime import date, datetime

import pytest

from leadintel.score import assign_tier, build_lead, compute_flags, score_company
from leadintel.settings import load_config

CFG = load_config("icp")
AS_OF = date(2026, 10, 31)


def row(**kw):
    base = {
        "domain": "brand.in", "name": "Brand", "vertical": "d2c", "funding_stage": None,
        "last_funding_date": None, "platform": "custom", "gateways_detected": [],
        "gateway_confidence": None, "checkout_layer": None, "has_subscription": False,
        "has_international": False, "has_cod": False, "has_emi": False, "has_android_app": False,
        "has_ios_app": False, "has_pricing_page": False, "contact_email": None, "pages_crawled": 3,
        "evidence": "{}",
    }  # fmt: skip
    return {**base, **kw}


def gw(name, level):
    return {
        "gateways_detected": [name],
        "gateway_confidence": level,
        "evidence": json.dumps({f"gateway:{name}": {"level": level}}),
    }


def test_known_d2c_lead_scores_as_expected():
    r = row(
        platform="shopify", has_cod=True, contact_email="hello@brand.in",
        funding_stage="A", last_funding_date=date(2026, 3, 1), **gw("razorpay", "high"),
    )  # fmt: skip
    score, contribs = score_company(r, CFG, AS_OF)
    # competitor 20 + single 10 + funding 20 + shopify 10 + cod 5 + email 5
    assert score == 70
    assert contribs[0].weight == 20
    assert assign_tier(score, compute_flags(r, AS_OF), CFG) == "A"


def test_empty_signals_score_zero_tier_c():
    score, contribs = score_company(row(), CFG, AS_OF)
    assert score == 0 and contribs == []
    assert assign_tier(score, compute_flags(row(), AS_OF), CFG) == "C"


@pytest.mark.parametrize("vertical", ["d2c", "edtech", "saas"])
def test_cashfree_users_never_tier_a(vertical):
    r = row(
        vertical=vertical, platform="shopify", has_subscription=True, has_international=True,
        has_cod=True, has_emi=True, has_android_app=True, contact_email="sales@brand.in",
        funding_stage="B+", last_funding_date=date(2026, 6, 1), **gw("cashfree", "high"),
    )  # fmt: skip
    lead = build_lead(r, CFG, AS_OF, datetime(2026, 10, 31))
    assert lead["tier"] == "C"
    assert lead["reasons"][0].startswith("Already on Cashfree")
    assert "Cashfree" in lead["opener"]


def test_scores_clipped_to_0_100():
    everything = row(
        vertical="saas", platform="shopify", has_subscription=True, has_international=True,
        has_pricing_page=True, contact_email="sales@brand.in", funding_stage="A",
        last_funding_date=date(2026, 6, 1), **gw("stripe", "high"),
    )  # fmt: skip
    assert 0 <= score_company(everything, CFG, AS_OF)[0] <= 100
    negative = row(**gw("cashfree", "high"))
    assert score_company(negative, CFG, AS_OF)[0] == 0


def test_low_confidence_gateway_does_not_count_as_competitor():
    flags = compute_flags(row(**gw("razorpay", "low")), AS_OF)
    assert not flags["competitor_gateway"] and not flags["single_gateway"]


def test_old_funding_not_recent():
    assert not compute_flags(row(last_funding_date=date(2024, 1, 1)), AS_OF)["recent_funding"]
    assert compute_flags(row(last_funding_date=date(2025, 6, 1)), AS_OF)["recent_funding"]


def test_magic_checkout_not_triple_counted():
    r = row(platform="shopify", checkout_layer="razorpay_magic", **gw("razorpay", "medium"))
    flags = compute_flags(r, AS_OF)
    assert flags["competitor_gateway"] and not flags["checkout_layer"]
    assert compute_flags(row(checkout_layer="gokwik"), AS_OF)["checkout_layer"]


def test_icp_follows_vertical_and_weights_differ():
    intl = row(has_international=True)
    assert score_company({**intl, "vertical": "saas"}, CFG, AS_OF)[0] == 30
    assert score_company({**intl, "vertical": "d2c"}, CFG, AS_OF)[0] == 10


def test_lead_has_top3_reasons_bant_and_products():
    r = row(
        vertical="edtech", has_subscription=True, has_android_app=True, has_emi=True,
        contact_email="hello@brand.in",
    )  # fmt: skip
    lead = build_lead(r, CFG, AS_OF, datetime(2026, 10, 31))
    assert lead["icp"] == "edtech_subscription"
    assert len(lead["reasons"]) == 3
    assert lead["reasons"][0] == "Sells subscriptions / recurring plans"
    assert lead["bant_need"].startswith("Recurring payments")
    assert "to verify on call" in lead["bant_authority"]
    assert "Subscriptions (UPI Autopay / e-mandate)" in lead["suggested_products"]
    assert len(lead["suggested_products"]) <= 3


def test_blocked_site_is_seed_only():
    lead = build_lead(row(pages_crawled=None), CFG, AS_OF, datetime(2026, 10, 31))
    assert lead["data_coverage"] == "seed_only"
    assert "research manually" in lead["reasons"][-1]
