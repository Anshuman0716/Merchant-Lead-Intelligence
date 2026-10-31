"""Small HTML helpers shared by the crawler and the detector."""

from __future__ import annotations

import gzip
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from selectolax.lexbor import LexborHTMLParser


def read_html(path: str | Path) -> str:
    p = Path(path)
    data = p.read_bytes()
    if p.suffix == ".gz":
        data = gzip.decompress(data)
    return data.decode("utf-8", errors="replace")


def write_html(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(html.encode("utf-8"), compresslevel=6))


@dataclass
class ParsedPage:
    """The parts of a page the fingerprint rules search in (all lowercased)."""

    html: str = ""  # raw HTML
    scripts: list[str] = field(default_factory=list)  # script/link/iframe src + inline script text
    links: list[str] = field(default_factory=list)  # absolute <a href> URLs
    images: list[str] = field(default_factory=list)  # img src + alt, svg titles
    text: str = ""  # visible text
    script_src_count: int = 0


def parse_page(html: str, base_url: str = "") -> ParsedPage:
    tree = LexborHTMLParser(html)
    scripts: list[str] = []
    src_count = 0
    for node in tree.css("script"):
        src = node.attributes.get("src")
        if src:
            scripts.append(src.lower())
            src_count += 1
        else:
            body = node.text(deep=True) or ""
            if body:
                scripts.append(body.lower())
    for node in tree.css("link[href], iframe[src]"):
        val = node.attributes.get("href") or node.attributes.get("src")
        if val:
            scripts.append(val.lower())

    links = []
    for node in tree.css("a[href]"):
        href = (node.attributes.get("href") or "").strip()
        if href and not href.startswith(("#", "javascript:")):
            links.append(urljoin(base_url, href) if base_url else href)

    images = []
    for node in tree.css("img"):
        for attr in ("src", "alt", "data-src", "title"):
            v = node.attributes.get(attr)
            if v:
                images.append(v.lower())
    for node in tree.css("svg title"):
        t = node.text(deep=True)
        if t:
            images.append(t.lower())

    for node in tree.css("script, style, noscript, template"):
        node.decompose()
    root = tree.body or tree.root
    text = root.text(separator=" ", strip=True).lower() if root else ""

    return ParsedPage(
        html=html.lower(),
        scripts=scripts,
        links=links,
        images=images,
        text=" ".join(text.split()),
        script_src_count=src_count,
    )


def same_site(url: str, domain: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host == domain or host.endswith("." + domain)
