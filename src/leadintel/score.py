"""Apply ICP weights, assign tier, reasons, BANT, products and opener -> lead_scores.

Scoring is a transparent rule system on purpose: a sales manager must be able to read why a
lead is Tier A, and change a weight in config/icp.yaml without touching code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime

import duckdb
import polars as pl

from leadintel.db import read_table, write_table
from leadintel.openers import GATEWAY_NAMES, LAYER_NAMES, TEMPLATES, make_opener
from leadintel.schemas import LeadScores
from leadintel.settings import load_config

STRONG = ("high", "medium")
PLATFORM_NAMES = {"shopify": "Shopify", "woocommerce": "WooCommerce"}


@dataclass
class Contribution:
    signal: str
    weight: int
    reason: str


def months_between(earlier: date, later: date) -> float:
    return (
        (later.year - earlier.year) * 12
        + (later.month - earlier.month)
        + (later.day - earlier.day) / 30
    )


def gateway_levels(row: dict) -> dict[str, str]:
    """{gateway: confidence} from the evidence JSON (falls back to the row-level confidence)."""
    ev = row.get("evidence") or {}
    if isinstance(ev, str):
        ev = json.loads(ev)
    out = {}
    for g in row.get("gateways_detected") or []:
        out[g] = (ev.get(f"gateway:{g}") or {}).get("level") or row.get("gateway_confidence")
    return out


def gateway_implying_layers() -> set[str]:
    layers = load_config("fingerprints").get("checkout_layers", {})
    return {name for name, rule in layers.items() if rule.get("implies_gateway")}


def compute_flags(row: dict, as_of: date, recent_months: int = 18) -> dict[str, bool]:
    """Which scoring signals are true for this company (row = companies + signals columns)."""
    levels = gateway_levels(row)
    competitors = [g for g, lvl in levels.items() if g != "cashfree" and lvl in STRONG]
    funded = row.get("last_funding_date")
    if isinstance(funded, str):
        funded = date.fromisoformat(funded)
    return {
        "competitor_gateway": bool(competitors),
        "single_gateway": len(levels) == 1 and bool(competitors),
        "uses_cashfree": "cashfree" in levels,
        # A layer that already told us the gateway (Razorpay Magic) is scored as a gateway
        # signal only, so one script isn't counted three times.
        "checkout_layer": bool(row.get("checkout_layer"))
        and row.get("checkout_layer") not in gateway_implying_layers(),
        "subscription": bool(row.get("has_subscription")),
        "international": bool(row.get("has_international")),
        "recent_funding": bool(funded) and 0 <= months_between(funded, as_of) <= recent_months,
        "shopify_woo": row.get("platform") in ("shopify", "woocommerce"),
        "mobile_app": bool(row.get("has_android_app") or row.get("has_ios_app")),
        "cod": bool(row.get("has_cod")),
        "emi": bool(row.get("has_emi")),
        "pricing_page": bool(row.get("has_pricing_page")),
        "contact_email": bool(row.get("contact_email")),
    }


def _reason_ctx(row: dict) -> dict:
    levels = gateway_levels(row)
    ordered = sorted(levels, key=lambda g: (g == "cashfree", -("high", "medium", "low").index(
        levels[g]) if levels[g] in ("high", "medium", "low") else 0))  # fmt: skip
    competitors = [g for g in ordered if g != "cashfree"]
    first = competitors[0] if competitors else (ordered[0] if ordered else "")
    return {
        "gateways": competitors or ordered,
        "gateway": GATEWAY_NAMES.get(first, first.title()),
        "confidence": levels.get(first, ""),
        "layer": row.get("checkout_layer"),
        "funding_stage": row.get("funding_stage"),
        "platform": PLATFORM_NAMES.get(row.get("platform") or "", row.get("platform") or ""),
    }


def score_company(row: dict, cfg: dict, as_of: date) -> tuple[int, list[Contribution]]:
    """Pure scoring function: (score 0-100, contributions sorted by impact)."""
    icp = cfg["icps"][cfg["vertical_to_icp"][row["vertical"]]]
    flags = compute_flags(row, as_of, cfg.get("recent_funding_months", 18))
    ctx = _reason_ctx(row)
    ctx["layer"] = LAYER_NAMES.get(ctx["layer"] or "", ctx["layer"] or "")
    order = list(cfg["signals"])
    contribs = [
        Contribution(sig, w, cfg["signals"][sig]["reason"].format(**ctx))
        for sig, w in icp["weights"].items()
        if flags.get(sig) and w != 0
    ]
    contribs.sort(key=lambda c: (c.weight > 0, -abs(c.weight), order.index(c.signal)))
    score = max(0, min(100, sum(c.weight for c in contribs)))
    return score, contribs


def assign_tier(score: int, flags: dict[str, bool], cfg: dict) -> str:
    if flags.get("uses_cashfree"):
        return "C"  # existing customer -> account manager, never an SDR priority
    if score >= cfg["tiers"]["A"]:
        return "A"
    if score >= cfg["tiers"]["B"]:
        return "B"
    return "C"


def suggest_products(row: dict, flags: dict[str, bool], cfg: dict) -> list[str]:
    icp = cfg["icps"][cfg["vertical_to_icp"][row["vertical"]]]
    products = list(icp["base_products"])
    for sig, product in cfg["product_map"].items():
        if flags.get(sig):
            if product.startswith("Payment Gateway") and "Payment Gateway" in products:
                products[products.index("Payment Gateway")] = product
            elif product not in products:
                products.append(product)
    return products[:3]


def bant(row: dict, flags: dict[str, bool], cfg: dict) -> dict[str, str]:
    icp = cfg["icps"][cfg["vertical_to_icp"][row["vertical"]]]
    stage = row.get("funding_stage")
    budget = {
        "B+": "Series B+ — budget likely available",
        "A": "Series A — likely has budget",
        "seed": "Seed-funded — budget-conscious; sell on success-rate ROI",
        "bootstrapped": "Bootstrapped — price-sensitive; lead with pricing",
    }.get(stage or "")
    if not budget:
        budget = (
            "Funding unknown; already pays for a checkout layer — spends on conversion"
            if flags["checkout_layer"]
            else "Unknown — to verify on call"
        )
    ctx = _reason_ctx(row)
    if flags["uses_cashfree"]:
        need = "Existing Cashfree merchant — expansion / health check"
    elif flags["single_gateway"]:
        need = f"Single gateway detected ({ctx['gateway']}) — no visible fallback route"
    elif flags["subscription"]:
        need = "Recurring payments — failed renewals and mandates"
    elif flags["international"]:
        need = "International customers — cross-border collection and FX"
    elif flags["emi"]:
        need = "EMI / instalments offered — collections and failed mandates"
    elif flags["cod"]:
        need = "COD offered — returns and prepaid conversion"
    elif flags["checkout_layer"]:
        layer = LAYER_NAMES.get(row.get("checkout_layer") or "", row.get("checkout_layer"))
        need = f"Optimising checkout conversion (uses {layer})"
    else:
        need = "Not clear from public data — discover on call"
    timeline = (
        "Scaling after funding — likely next 1–2 quarters"
        if flags["recent_funding"]
        else "Unknown — ask on call"
    )
    return {
        "bant_budget": budget,
        "bant_authority": f"{icp['buyer']} (to verify on call)",
        "bant_need": need,
        "bant_timeline": timeline,
    }


def pick_opener_signal(contribs: list[Contribution], flags: dict[str, bool]) -> str | None:
    if flags.get("uses_cashfree"):
        return "uses_cashfree"
    for c in contribs:
        if c.weight > 0 and c.signal in TEMPLATES:
            return c.signal
    return None


def build_lead(row: dict, cfg: dict, as_of: date, scored_at: datetime) -> dict:
    seed_only = not row.get("pages_crawled")
    score, contribs = score_company(row, cfg, as_of)
    flags = compute_flags(row, as_of, cfg.get("recent_funding_months", 18))
    reasons = [c.reason for c in contribs][:3]
    if seed_only:
        reasons = [*reasons[:2], cfg["signals"]["seed_only"]["reason"]]
    if not reasons:
        reasons = ["No strong buying signals found on public pages"]
    ctx = _reason_ctx(row)
    return {
        "domain": row["domain"],
        "icp": cfg["vertical_to_icp"][row["vertical"]],
        "score": score,
        "tier": assign_tier(score, flags, cfg),
        "reasons": reasons,
        **bant(row, flags, cfg),
        "suggested_products": suggest_products(row, flags, cfg),
        "opener": make_opener(row["name"], pick_opener_signal(contribs, flags), ctx),
        "data_coverage": "seed_only" if seed_only else "website",
        "scored_at": scored_at,
    }


def run(conn: duckdb.DuckDBPyConnection, as_of: date | None = None, **kwargs) -> str:
    cfg = load_config("icp")
    as_of = as_of or date.today()
    companies = read_table("companies", conn)
    # Valid sites, plus sites that block bots: those are still scored on seed data
    companies = companies.filter(
        pl.col("is_valid") | pl.col("quarantine_reason").str.starts_with("blocked")
    )
    signals = read_table("signals", conn)
    rows = companies.join(signals, on="domain", how="left").to_dicts()
    scored_at = datetime.now().replace(microsecond=0)
    leads = [build_lead(r, cfg, as_of, scored_at) for r in rows]
    df = pl.DataFrame(
        leads,
        schema_overrides={"reasons": pl.List(pl.Utf8), "suggested_products": pl.List(pl.Utf8)},
    )
    df = LeadScores.validate(df.select(list(LeadScores.to_schema().columns)))
    write_table(df, "lead_scores", conn)

    tiers = dict(df["tier"].value_counts().iter_rows())
    n = df.height
    split = ", ".join(f"{t}={tiers.get(t, 0)} ({tiers.get(t, 0) / n:.0%})" for t in "ABC")
    return f"lead_scores: {n} leads; tiers {split}; median score {int(df['score'].median())}"
