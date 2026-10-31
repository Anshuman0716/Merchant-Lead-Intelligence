"""Run fingerprint rules on cached HTML -> signals (one row per company, with evidence)."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cache

import duckdb
import polars as pl

from leadintel.db import read_table, write_table
from leadintel.htmlparse import ParsedPage, parse_page, read_html
from leadintel.schemas import Signals
from leadintel.settings import ROOT, load_config

LEVEL_RANK = {"high": 3, "medium": 2, "low": 1}
WHERE_LEVEL = {"script": "high", "html": "high", "links": "high", "img": "low", "text": "low"}
EMAIL_RE = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}")


@dataclass
class Match:
    where: str
    pattern: str
    page: str

    @property
    def level(self) -> str:
        return WHERE_LEVEL[self.where]


@cache
def _compile(pattern: str) -> re.Pattern:
    return re.compile(pattern)


def _in_payment_context(pattern: str, text: str, ctx: dict) -> bool:
    """True if a text match sits next to payment words (ignoring '<name> payments' as a phrase)."""
    word = _compile(ctx["text_context"])
    for m in _compile(pattern).finditer(text):
        before = text[max(0, m.start() - ctx["context_chars_before"]) : m.start()]
        after = text[m.end() : m.end() + ctx["context_chars_after"]]
        after = re.sub(r"^\s*payments\b", "", after)  # "Cashfree Payments" is a company name
        if word.search(before) or word.search(after):
            return True
    return False


def match_rule(
    rule: dict, page: ParsedPage, page_type: str, low_ctx: dict | None = None
) -> Match | None:
    """Return the strongest match of a rule on one page, or None.

    low_ctx (gateway rules only): text/img matches must be in a payment context.
    """
    for where in ("script", "html", "links", "img", "text"):
        for pat in rule.get(where, []) or []:
            pat_l = pat.lower()
            if where == "script":
                hit = any(pat_l in s for s in page.scripts)
            elif where == "html":
                hit = pat_l in page.html
            elif where == "links":
                hit = any(pat_l in u.lower() for u in page.links)
            elif where == "img":
                need = (low_ctx or {}).get("img_must_contain", "")
                hit = any(
                    pat_l in s and need in s.replace(f"{pat_l} payments", "") for s in page.images
                )
            elif low_ctx:
                hit = _in_payment_context(pat, page.text, low_ctx)
            else:
                hit = _compile(pat).search(page.text) is not None
            if hit:
                return Match(where, pat, page_type)
    return None


def best_match(
    rule: dict, pages: dict[str, ParsedPage], low_ctx: dict | None = None
) -> Match | None:
    best = None
    for ptype, page in pages.items():
        m = match_rule(rule, page, ptype, low_ctx)
        if m and (best is None or LEVEL_RANK[m.level] > LEVEL_RANK[best.level]):
            best = m
    return best


def extract_contact_email(
    pages: dict[str, ParsedPage], domains: Iterable[str], prefixes: list[str]
):
    """Public role-style business email on the company's own domain, or None."""
    domains = {d for d in domains if d}
    found: set[str] = set()
    for ptype in ("contact", "home"):
        page = pages.get(ptype)
        if not page:
            continue
        found.update(EMAIL_RE.findall(page.text))
        found.update(
            u[7:].split("?")[0].strip().lower()
            for u in page.links
            if u.lower().startswith("mailto:")
        )

    def own(email: str) -> bool:
        host = email.rsplit("@", 1)[-1]
        return any(host == d or host.endswith("." + d) for d in domains)

    def rank(email: str) -> int | None:
        local = email.split("@", 1)[0]
        for i, p in enumerate(prefixes):
            if (
                local == p
                or local.startswith(p + ".")
                or local.startswith(p + "_")
                or local == p + "s"
            ):
                return i
        return None

    candidates = [(rank(e), e) for e in found if own(e) and rank(e) is not None]
    return min(candidates)[1] if candidates else None


@dataclass
class DomainSignals:
    domain: str
    platform: str = "unknown"
    gateways_detected: list[str] = field(default_factory=list)
    gateway_confidence: str | None = None
    checkout_layer: str | None = None
    has_subscription: bool = False
    has_international: bool = False
    has_cod: bool = False
    has_android_app: bool = False
    has_ios_app: bool = False
    has_pricing_page: bool = False
    contact_email: str | None = None
    pages_crawled: int = 0
    evidence: dict = field(default_factory=dict)


def detect_domain(
    domain: str, pages: dict[str, ParsedPage], rules: dict, extra_domains: Iterable[str] = ()
) -> DomainSignals:
    s = DomainSignals(domain=domain, pages_crawled=len(pages))
    if not pages:
        return s

    def ev(key: str, m: Match, level: str | None = None) -> None:
        s.evidence[key] = {"page": m.page, "where": m.where, "match": m.pattern,
                           "level": level or m.level}  # fmt: skip

    s.platform = "custom"
    for name, rule in rules["platforms"].items():
        if m := best_match(rule, pages):
            s.platform = name
            ev(f"platform:{name}", m)
            break

    own_labels = {d.split(".")[0] for d in (domain, *extra_domains) if d}

    def is_vendor(rule_name: str) -> bool:
        """chargebee.com is not 'using Chargebee'; razorpay_magic -> vendor 'razorpay'."""
        return rule_name.split("_")[0] in own_labels

    low_ctx = rules.get("gateway_low_confidence")
    gw_levels: dict[str, str] = {}
    for name, rule in rules["gateways"].items():
        if not is_vendor(name) and (m := best_match(rule, pages, low_ctx)):
            gw_levels[name] = m.level
            ev(f"gateway:{name}", m)

    for name, rule in rules["checkout_layers"].items():
        if not is_vendor(name) and (m := best_match(rule, pages)):
            s.checkout_layer = name
            ev(f"checkout:{name}", m)
            implied = rule.get("implies_gateway")
            if implied and LEVEL_RANK.get(gw_levels.get(implied, ""), 0) < LEVEL_RANK["medium"]:
                gw_levels[implied] = "medium"
                ev(f"gateway:{implied}", m, level="medium")
            break

    s.gateways_detected = sorted(gw_levels, key=lambda g: (-LEVEL_RANK[gw_levels[g]], g))
    if gw_levels:
        s.gateway_confidence = max(gw_levels.values(), key=LEVEL_RANK.get)

    feats = rules["features"]
    for attr, key in [("has_subscription", "subscription"), ("has_international", "international"),
                      ("has_cod", "cod"), ("has_android_app", "android_app"),
                      ("has_ios_app", "ios_app")]:  # fmt: skip
        if m := best_match(feats[key], pages):
            setattr(s, attr, True)
            ev(f"feature:{key}", m)

    if "pricing" in pages:
        s.has_pricing_page = True
        s.evidence["feature:pricing_page"] = {"page": "pricing", "where": "page", "match": "200 OK"}

    s.contact_email = extract_contact_email(
        pages, [domain, *extra_domains], rules.get("contact_email_prefixes", [])
    )
    return s


def load_pages(pages_df: pl.DataFrame, domain: str) -> dict[str, ParsedPage]:
    out = {}
    rows = pages_df.filter((pl.col("domain") == domain) & pl.col("html_path").is_not_null())
    for r in rows.iter_rows(named=True):
        out[r["page_type"]] = parse_page(read_html(ROOT / r["html_path"]), r["url"])
    return out


def to_frame(rows: list[DomainSignals]) -> pl.DataFrame:
    data = [{**s.__dict__, "evidence": json.dumps(s.evidence, sort_keys=True)} for s in rows]
    df = pl.DataFrame(data, schema_overrides={"gateways_detected": pl.List(pl.Utf8)})
    return Signals.validate(df.select(list(Signals.to_schema().columns)))


def run(conn: duckdb.DuckDBPyConnection, **kwargs) -> str:
    rules = load_config("fingerprints")
    companies = read_table("companies", conn).filter(pl.col("is_valid"))
    pages_df = read_table("pages", conn)
    results = []
    for c in companies.iter_rows(named=True):
        final_host = c["homepage_url"].split("/")[2] if "//" in c["homepage_url"] else ""
        extra = [final_host.removeprefix("www.")]
        results.append(detect_domain(c["domain"], load_pages(pages_df, c["domain"]), rules, extra))
    df = to_frame(results)
    write_table(df, "signals", conn)

    crawled = df.filter(pl.col("pages_crawled") > 0)
    n = max(crawled.height, 1)
    plat = ", ".join(f"{p}={k}" for p, k in crawled["platform"].value_counts(sort=True).iter_rows())
    gw = crawled.filter(pl.col("gateways_detected").list.len() > 0).height
    co = crawled.filter(pl.col("checkout_layer").is_not_null()).height
    em = crawled.filter(pl.col("contact_email").is_not_null()).height
    return (f"signals: {df.height} companies ({crawled.height} crawled). platform: {plat}; "
            f"gateway {gw / n:.0%}, checkout layer {co / n:.0%}, email {em / n:.0%}")  # fmt: skip
