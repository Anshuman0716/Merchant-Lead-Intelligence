"""Pandera schemas, one per pipeline table. Each stage validates its output before writing."""

from __future__ import annotations

import pandera.polars as pa
import polars as pl

VERTICALS = ["d2c", "edtech", "saas"]
FUNDING_STAGES = ["bootstrapped", "seed", "A", "B+"]
PAGE_TYPES = ["home", "product", "cart", "pricing", "contact"]
PLATFORMS = ["shopify", "woocommerce", "magento", "custom", "unknown"]
ICPS = ["d2c_growth", "edtech_subscription", "saas_global"]
TIERS = ["A", "B", "C"]
CONFIDENCE = ["high", "medium", "low"]

_DOMAIN_RE = r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$"


class RawCompanies(pa.DataFrameModel):
    name: str = pa.Field(str_length={"min_value": 1})
    url: str = pa.Field(str_length={"min_value": 3})
    vertical: str = pa.Field(isin=VERTICALS)
    sub_category: str = pa.Field(nullable=True)
    city: str = pa.Field(nullable=True)
    source: str = pa.Field(nullable=True)
    funding_stage: str = pa.Field(nullable=True, isin=FUNDING_STAGES)
    last_funding_date: pl.Date = pa.Field(nullable=True)
    source_file: str

    class Config:
        strict = True
        coerce = True


class Companies(pa.DataFrameModel):
    domain: str = pa.Field(unique=True, str_matches=_DOMAIN_RE)
    name: str
    vertical: str = pa.Field(isin=VERTICALS)
    sub_category: str = pa.Field(nullable=True)
    city: str = pa.Field(nullable=True)
    source: str = pa.Field(nullable=True)
    funding_stage: str = pa.Field(nullable=True, isin=FUNDING_STAGES)
    last_funding_date: pl.Date = pa.Field(nullable=True)
    homepage_url: str  # final URL after redirects; the crawler starts here
    is_valid: bool
    quarantine_reason: str = pa.Field(nullable=True)

    class Config:
        strict = True
        coerce = True


class Pages(pa.DataFrameModel):
    domain: str
    page_type: str = pa.Field(isin=PAGE_TYPES)
    url: str
    status_code: int = pa.Field(nullable=True)
    fetched_at: pl.Datetime = pa.Field(nullable=True)
    html_path: str = pa.Field(nullable=True)
    render_mode: str = pa.Field(isin=["static", "playwright", "cache", "skipped"])
    note: str = pa.Field(nullable=True)

    class Config:
        strict = True
        coerce = True


class Signals(pa.DataFrameModel):
    domain: str = pa.Field(unique=True)
    platform: str = pa.Field(isin=PLATFORMS)
    gateways_detected: pl.List(pl.Utf8)
    gateway_confidence: str = pa.Field(nullable=True, isin=CONFIDENCE)
    checkout_layer: str = pa.Field(nullable=True)
    has_subscription: bool
    has_international: bool
    has_cod: bool
    has_android_app: bool
    has_ios_app: bool
    has_pricing_page: bool
    contact_email: str = pa.Field(nullable=True)
    pages_crawled: int = pa.Field(ge=0)
    evidence: str  # JSON string

    class Config:
        strict = True
        coerce = True


class LeadScores(pa.DataFrameModel):
    domain: str = pa.Field(unique=True)
    icp: str = pa.Field(isin=ICPS)
    score: int = pa.Field(ge=0, le=100)
    tier: str = pa.Field(isin=TIERS)
    reasons: pl.List(pl.Utf8)
    bant_budget: str
    bant_authority: str
    bant_need: str
    bant_timeline: str
    suggested_products: pl.List(pl.Utf8)
    opener: str = pa.Field(str_length={"min_value": 1})
    scored_at: pl.Datetime

    class Config:
        strict = True
        coerce = True
