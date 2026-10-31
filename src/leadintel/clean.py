"""Normalise and dedupe companies, check reachability -> companies.

Rule carried over from Tapetide: quarantine, don't delete. Bad rows stay in the table with
is_valid = False and a quarantine_reason, so they can be reviewed.
"""

from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import urlsplit

import duckdb
import httpx
import polars as pl

from leadintel.db import read_table, write_table
from leadintel.schemas import Companies
from leadintel.settings import DATA_DIR, load_config

REACHABILITY_CACHE = DATA_DIR / "cache" / "reachability.json"

# Links to these mean the seed row points at a marketplace/social page, not the brand's own site
MARKETPLACES = {
    "amazon.in", "amazon.com", "flipkart.com", "myntra.com", "nykaa.com/brands",
    "instagram.com", "facebook.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "meesho.com", "ajio.com", "jiomart.com", "bigbasket.com",
    "play.google.com", "apps.apple.com", "linktr.ee",
}  # fmt: skip

_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://")


def normalise_domain(url: str | None) -> str | None:
    """'HTTPS://www.Brand.in/shop?x=1' -> 'brand.in'. Returns None if nothing usable."""
    if not url:
        return None
    s = url.strip().lower()
    if not _SCHEME_RE.match(s):
        s = "http://" + s.lstrip("/")
    host = urlsplit(s).hostname or ""
    host = host.strip(".")
    if host.startswith("www."):
        host = host[4:]
    if "." not in host:
        return None
    return host


def is_marketplace(domain: str) -> bool:
    return any(domain == m or domain.endswith("." + m) for m in MARKETPLACES if "/" not in m)


def dedupe(df: pl.DataFrame) -> pl.DataFrame:
    """One row per domain; when duplicates disagree keep the row with more filled fields."""
    filled = pl.sum_horizontal([pl.col(c).is_not_null().cast(pl.Int32) for c in df.columns])
    return (
        df.with_columns(_filled=filled, _order=pl.int_range(pl.len()))
        .sort(["domain", "_filled", "_order"], descending=[False, True, False])
        .unique(subset="domain", keep="first", maintain_order=True)
        .sort("_order")
        .drop("_filled", "_order")
    )


# ---------- reachability ----------


def _classify(status: int | None, error: str | None) -> str | None:
    """Return a quarantine reason, or None if the site is fine."""
    if error:
        return "unreachable"
    if status is None:
        return "unreachable"
    if 200 <= status < 400:
        return None
    if status in (401, 403, 429, 503):
        return f"blocked_{status}"  # respect it: don't try to bypass bot protection
    return f"http_{status}"


async def _check_one(client: httpx.AsyncClient, domain: str, sem: asyncio.Semaphore) -> dict:
    async with sem:
        last: dict = {"domain": domain, "status": None, "final_url": None, "error": "no attempt"}
        for host in (domain, f"www.{domain}"):
            try:
                r = await client.get(f"https://{host}/")
                last = {"domain": domain, "status": r.status_code,
                        "final_url": str(r.url), "error": None}  # fmt: skip
                if r.status_code < 400:
                    return last
            except httpx.HTTPError as e:
                last = {"domain": domain, "status": None, "final_url": None,
                        "error": type(e).__name__}  # fmt: skip
        return last


async def _check_all(domains: list[str], timeout_multiplier: float = 1.0) -> list[dict]:
    cfg = load_config("crawl")
    rc = cfg.get("reachability", {})
    sem = asyncio.Semaphore(rc.get("concurrency", 20))
    headers = {"User-Agent": cfg["user_agent"], "Accept": "text/html,*/*;q=0.8"}
    timeout = httpx.Timeout(rc.get("timeout_seconds", 5) * timeout_multiplier)
    async with httpx.AsyncClient(
        headers=headers, timeout=timeout, follow_redirects=True, max_redirects=5
    ) as client:
        return await asyncio.gather(*[_check_one(client, d, sem) for d in domains])


def check_reachability(domains: list[str], refresh: bool = False, skip_network: bool = False):
    """Return {domain: result}. Results are cached in data/cache/reachability.json."""
    cache: dict[str, dict] = {}
    if REACHABILITY_CACHE.exists() and not refresh:
        cache = json.loads(REACHABILITY_CACHE.read_text(encoding="utf-8"))
    todo = [d for d in domains if d not in cache]
    if todo and not skip_network:
        for res in asyncio.run(_check_all(todo)):
            cache[res["domain"]] = res
        # One slower retry for network errors, so a single slow response doesn't quarantine a site
        failed = [d for d in todo if cache[d].get("error")]
        if failed:
            for res in asyncio.run(_check_all(failed, timeout_multiplier=3)):
                cache[res["domain"]] = res
        REACHABILITY_CACHE.parent.mkdir(parents=True, exist_ok=True)
        REACHABILITY_CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True), "utf-8")
    return cache


# ---------- stage ----------


def build_companies(raw: pl.DataFrame, reach: dict[str, dict] | None = None) -> pl.DataFrame:
    df = raw.with_columns(
        domain=pl.col("url").map_elements(normalise_domain, return_dtype=pl.Utf8),
        name=pl.col("name").str.strip_chars(),
        sub_category=pl.col("sub_category").str.to_lowercase(),
        city=pl.col("city").str.to_titlecase(),
    ).filter(pl.col("domain").is_not_null())
    df = dedupe(df)

    reach = reach or {}

    # A site that redirects to another company's domain in the list is the same business
    # (e.g. acquired brand). Keep the target, quarantine the redirecting row.
    known = set(df["domain"])
    redirect_dupe: dict[str, str] = {}
    seen_final: dict[str, str] = {}
    for d in df["domain"]:
        final = normalise_domain((reach.get(d) or {}).get("final_url"))
        if not final or final == d:
            continue
        if final in known:
            redirect_dupe[d] = final
        elif final in seen_final:
            redirect_dupe[d] = seen_final[final]
        else:
            seen_final[final] = d

    def reason(domain: str) -> str | None:
        if is_marketplace(domain):
            return "not_own_site"
        if domain in redirect_dupe:
            return f"duplicate_of:{redirect_dupe[domain]}"
        r = reach.get(domain)
        if r is None:
            return None  # not checked (offline run) -> assume valid
        return _classify(r.get("status"), r.get("error"))

    def homepage(domain: str) -> str:
        r = reach.get(domain) or {}
        return r.get("final_url") or f"https://{domain}/"

    df = df.with_columns(
        quarantine_reason=pl.col("domain").map_elements(reason, return_dtype=pl.Utf8),
        homepage_url=pl.col("domain").map_elements(homepage, return_dtype=pl.Utf8),
    ).with_columns(is_valid=pl.col("quarantine_reason").is_null())

    cols = list(Companies.to_schema().columns)
    return Companies.validate(df.select(cols))


def run(conn: duckdb.DuckDBPyConnection, refresh: bool = False, skip_network: bool = False,
        **kwargs) -> str:  # fmt: skip
    raw = read_table("raw_companies", conn)
    domains = [d for d in (normalise_domain(u) for u in raw["url"]) if d and not is_marketplace(d)]
    reach = check_reachability(sorted(set(domains)), refresh=refresh, skip_network=skip_network)
    df = build_companies(raw, reach)
    write_table(df, "companies", conn)

    valid = df.filter(pl.col("is_valid"))
    counts = valid.group_by("vertical").len().sort("vertical")
    per_v = ", ".join(f"{v}={n}" for v, n in counts.iter_rows())
    q = df.filter(~pl.col("is_valid"))["quarantine_reason"].value_counts(sort=True)
    q_txt = ", ".join(f"{r}={n}" for r, n in q.iter_rows()) or "none"
    dupes = raw.height - df.height
    return (f"companies: {df.height} unique ({dupes} dupes dropped), {valid.height} valid "
            f"({per_v}); quarantined: {q_txt}")  # fmt: skip
