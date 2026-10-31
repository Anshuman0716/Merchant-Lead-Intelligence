"""Polite crawler: fetch a few public pages per domain, cache to disk -> pages.

Ethics: only public pages, robots.txt respected, max 1 request / 2 s per domain, honest user
agent, no logins, no form submissions, no checkout attempts.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import duckdb
import httpx
import polars as pl
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_fixed

from leadintel.db import read_table, write_table
from leadintel.htmlparse import parse_page, read_html, same_site, write_html
from leadintel.schemas import Pages
from leadintel.settings import CACHE_DIR, ROOT, load_config

MAX_BYTES = 3_000_000
BOT_TOKEN = "LeadIntelBot"


def domain_dir(domain: str) -> Path:
    return CACHE_DIR / domain


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def pick_link(links: list[str], patterns: list[str], domain: str, site: str) -> str | None:
    """First internal link whose path contains a pattern (patterns checked in priority order)."""
    internal = [u for u in links if same_site(u, domain) or same_site(u, site)]
    for pat in patterns:
        for u in internal:
            path = urlsplit(u).path.lower()
            if pat in path and path.rstrip("/") != pat.rstrip("/"):
                return u.split("#")[0]
    return None


class DomainCrawler:
    def __init__(self, client: httpx.AsyncClient, cfg: dict, domain: str, homepage: str):
        self.client = client
        self.cfg = cfg
        self.domain = domain
        self.homepage = homepage
        parts = urlsplit(homepage)
        self.base = f"{parts.scheme}://{parts.netloc}"
        self.site = (parts.hostname or domain).removeprefix("www.")
        self.robots: RobotFileParser | None = None
        self.robots_blocks_all = False
        self._last = 0.0
        self.rows: list[dict] = []

    async def _wait_turn(self) -> None:
        delay = self.cfg["min_delay_per_domain_seconds"]
        wait = self._last + delay - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        self._last = time.monotonic()

    async def _get(self, url: str) -> httpx.Response:
        await self._wait_turn()
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.cfg["retries"] + 1),
            wait=wait_fixed(2),
            retry=retry_if_exception_type(httpx.TransportError),
            reraise=True,
        ):
            with attempt:
                return await self.client.get(url)
        raise RuntimeError("unreachable")  # pragma: no cover

    async def load_robots(self) -> None:
        rp = RobotFileParser()
        try:
            r = await self._get(f"{self.base}/robots.txt")
            if r.status_code >= 500:
                self.robots_blocks_all = True
            elif r.status_code == 200:
                rp.parse(r.text.splitlines())
            else:
                rp.parse([])  # 4xx -> no rules, everything allowed
        except httpx.HTTPError:
            rp.parse([])
        self.robots = rp

    def allowed(self, url: str) -> bool:
        if self.robots_blocks_all:
            return False
        return self.robots is None or self.robots.can_fetch(BOT_TOKEN, url)

    async def fetch(self, page_type: str, url: str, record_failure: bool = True) -> str | None:
        row = {
            "domain": self.domain, "page_type": page_type, "url": url, "status_code": None,
            "fetched_at": None, "html_path": None, "render_mode": "static", "note": None,
        }  # fmt: skip
        if not self.allowed(url):
            row.update(render_mode="skipped", note="robots_disallowed")
            self.rows.append(row)
            return None
        try:
            r = await self._get(url)
        except httpx.HTTPError as e:
            row.update(note=type(e).__name__)
            if record_failure:
                self.rows.append(row)
            return None
        row.update(
            status_code=r.status_code,
            url=str(r.url),
            fetched_at=datetime.now(UTC).replace(tzinfo=None),
        )
        ctype = r.headers.get("content-type", "")
        if r.status_code != 200 or "html" not in ctype:
            row["note"] = None if r.status_code != 200 else f"not_html:{ctype[:40]}"
            if record_failure:
                self.rows.append(row)
            return None
        html = r.text[:MAX_BYTES]
        html = await self._maybe_render(url, html, row)
        path = domain_dir(self.domain) / f"{page_type}.html.gz"
        write_html(path, html)
        row["html_path"] = _rel(path)
        self.rows.append(row)
        return html

    async def _maybe_render(self, url: str, html: str, row: dict) -> str:
        pw = self.cfg.get("playwright_fallback", {})
        if not pw.get("enabled"):
            return html
        looks_empty = (
            len(html) < pw.get("min_html_bytes", 5000) or "<script src" not in html.lower()
        )
        if not looks_empty:
            return html
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return html
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(user_agent=self.cfg["user_agent"])
            await page.goto(url, timeout=self.cfg["timeout_seconds"] * 1000)
            await page.wait_for_load_state("networkidle")
            rendered = await page.content()
            await browser.close()
        row["render_mode"] = "playwright"
        return rendered

    async def crawl(self) -> list[dict]:
        await self.load_robots()
        home = await self.fetch("home", self.homepage)
        links = parse_page(home, self.homepage).links if home else []

        product = pick_link(links, self.cfg["product_link_patterns"], self.domain, self.site)
        if product:
            await self.fetch("product", product)

        await self.fetch("cart", urljoin(self.base, self.cfg["pages"]["cart"]))

        pricing = pick_link(links, ["/pricing", "/plans"], self.domain, self.site)
        await self.fetch("pricing", pricing or urljoin(self.base, self.cfg["pages"]["pricing"]))

        contact = pick_link(links, ["/contact"], self.domain, self.site)
        if contact:
            await self.fetch("contact", contact)
        else:
            paths = [self.cfg["pages"]["contact"], *self.cfg["contact_fallback_paths"]]
            for i, p in enumerate(paths):
                last = i == len(paths) - 1
                if await self.fetch("contact", urljoin(self.base, p), record_failure=last):
                    break
        return self.rows


async def _crawl_all(companies: list[dict], refresh: bool) -> list[dict]:
    cfg = load_config("crawl")
    sem = asyncio.Semaphore(cfg["concurrent_domains"])
    headers = {"User-Agent": cfg["user_agent"], "Accept": "text/html,application/xhtml+xml"}
    timeout = httpx.Timeout(cfg["timeout_seconds"])
    done = 0
    all_rows: list[dict] = []

    async def one(c: dict) -> None:
        nonlocal done
        meta = domain_dir(c["domain"]) / "_meta.json"
        if meta.exists() and not refresh:
            rows = json.loads(meta.read_text("utf-8"))
        else:
            async with sem:
                rows = await DomainCrawler(client, cfg, c["domain"], c["homepage_url"]).crawl()
            meta.parent.mkdir(parents=True, exist_ok=True)
            meta.write_text(json.dumps(rows, default=str, indent=1), "utf-8")
        all_rows.extend(rows)
        done += 1
        if done % 25 == 0 or done == len(companies):
            print(f"  crawled {done}/{len(companies)}", flush=True)

    async with httpx.AsyncClient(
        headers=headers, timeout=timeout, follow_redirects=True, max_redirects=5
    ) as client:
        await asyncio.gather(*[one(c) for c in companies])
    return all_rows


def load_cached_rows(domains: list[str]) -> list[dict]:
    rows = []
    for d in domains:
        meta = domain_dir(d) / "_meta.json"
        if meta.exists():
            rows.extend(json.loads(meta.read_text("utf-8")))
    return rows


def run(conn: duckdb.DuckDBPyConnection, refresh: bool = False, limit: int | None = None,
        skip_network: bool = False, **kwargs) -> str:  # fmt: skip
    companies = read_table("companies", conn).filter(pl.col("is_valid"))
    if limit:
        companies = companies.head(limit)
    targets = companies.select("domain", "homepage_url").to_dicts()

    if skip_network:
        rows = load_cached_rows([t["domain"] for t in targets])
    else:
        rows = asyncio.run(_crawl_all(targets, refresh))

    if not rows:
        return "pages: nothing crawled"
    rows = [{**r, "fetched_at": str(r["fetched_at"]) if r["fetched_at"] else None} for r in rows]
    df = pl.DataFrame(rows, infer_schema_length=None).with_columns(
        pl.col("fetched_at").cast(pl.Utf8).str.to_datetime(strict=False),
        pl.col("status_code").cast(pl.Int64),
    )
    df = Pages.validate(df.select(list(Pages.to_schema().columns)))
    write_table(df, "pages", conn)

    ok = df.filter(pl.col("html_path").is_not_null())
    with_home = ok.filter(pl.col("page_type") == "home")["domain"].n_unique()
    per_type = ", ".join(
        f"{t}={n}" for t, n in ok.group_by("page_type").len().sort("page_type").iter_rows()
    )
    robots = df.filter(pl.col("note") == "robots_disallowed").height
    return (f"pages: {df.height} fetch rows, {ok.height} cached ({per_type}); "
            f"{with_home}/{len(targets)} with homepage; {robots} robots-disallowed")  # fmt: skip


def cached_html(html_path: str) -> str:
    return read_html(ROOT / html_path)
