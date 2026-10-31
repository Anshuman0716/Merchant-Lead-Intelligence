from datetime import date

import polars as pl
import pytest

from leadintel.clean import build_companies, dedupe, is_marketplace, normalise_domain


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://mamaearth.in", "mamaearth.in"),
        ("https://www.mamaearth.in/", "mamaearth.in"),
        ("HTTP://WWW.Mamaearth.IN/shop?utm=1", "mamaearth.in"),
        ("mamaearth.in", "mamaearth.in"),
        ("www.mamaearth.in/collections/face", "mamaearth.in"),
        ("  https://mamaearth.in/  ", "mamaearth.in"),
        ("//mamaearth.in", "mamaearth.in"),
        ("https://shop.brand.co.in/products/x#top", "shop.brand.co.in"),
        ("https://brand.com:443/path", "brand.com"),
        ("not a url", None),
        ("", None),
        (None, None),
    ],
)
def test_normalise_domain(url, expected):
    assert normalise_domain(url) == expected


def test_marketplace_detection():
    assert is_marketplace("amazon.in")
    assert is_marketplace("instagram.com")
    assert is_marketplace("m.facebook.com")
    assert not is_marketplace("mamaearth.in")
    assert not is_marketplace("notamazon.in")


def test_dedupe_keeps_richer_row():
    df = pl.DataFrame(
        {
            "domain": ["a.in", "a.in", "b.in"],
            "city": [None, "Mumbai", "Pune"],
            "funding_stage": [None, "A", None],
        }
    )
    out = dedupe(df)
    assert out.height == 2
    assert out.filter(pl.col("domain") == "a.in")["city"][0] == "Mumbai"


def _raw(rows):
    base = {
        "vertical": "d2c", "sub_category": "beauty", "city": None, "source": "test",
        "funding_stage": None, "last_funding_date": None, "source_file": "t.csv",
    }  # fmt: skip
    return pl.DataFrame([{**base, **r} for r in rows]).with_columns(
        pl.col("last_funding_date").cast(pl.Date)
    )


def test_build_companies_quarantines_and_dedupes():
    raw = _raw(
        [
            {"name": "Brand", "url": "https://brand.in"},
            {
                "name": "Brand",
                "url": "www.brand.in/",
                "city": "Delhi",
                "funding_stage": "A",
                "last_funding_date": date(2026, 1, 1),
            },  # fmt: skip
            {"name": "Brand on Amazon", "url": "https://www.amazon.in/stores/brand"},
            {"name": "Blocked", "url": "blocked.in"},
            {"name": "Dead", "url": "dead.in"},
            {"name": "Acquired", "url": "old.in"},
        ]
    )
    reach = {
        "brand.in": {"status": 200, "final_url": "https://www.brand.in/", "error": None},
        "blocked.in": {"status": 403, "final_url": "https://blocked.in/", "error": None},
        "dead.in": {"status": None, "final_url": None, "error": "ConnectError"},
        "old.in": {"status": 200, "final_url": "https://brand.in/old", "error": None},
    }
    out = build_companies(raw, reach)
    by = {r["domain"]: r for r in out.iter_rows(named=True)}

    assert len(by) == 5  # brand.in deduped
    assert by["brand.in"]["is_valid"] and by["brand.in"]["city"] == "Delhi"
    assert by["amazon.in"]["quarantine_reason"] == "not_own_site"
    assert by["blocked.in"]["quarantine_reason"] == "blocked_403"
    assert by["dead.in"]["quarantine_reason"] == "unreachable"
    assert by["old.in"]["quarantine_reason"] == "duplicate_of:brand.in"
