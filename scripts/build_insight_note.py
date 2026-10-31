"""Build docs/insight_note.pdf (one page) from exports/leads.parquet.

    uv run --with reportlab python scripts/build_insight_note.py

Every number is computed from the export, so the note stays in sync with the dashboard.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "insight_note.pdf"
BLUE, INK, INK_2, RULE = "#184f95", "#0b0b0b", "#52514e", "#e4e2dd"


def pct(a: int, b: int) -> str:
    return f"{a / b:.0%}" if b else "0%"


def stats() -> dict:
    df = pl.read_parquet(ROOT / "exports" / "leads.parquet")
    web = df.filter(pl.col("data_coverage") == "website")
    d2c = web.filter(pl.col("vertical") == "d2c")
    saas = web.filter(pl.col("vertical") == "saas")
    edtech = web.filter(pl.col("vertical") == "edtech")
    shopify = web.filter(pl.col("platform") == "shopify")
    has_gw = web.filter(pl.col("gateways_detected").list.len() > 0)
    tier_a = df.filter(pl.col("tier") == "A")
    single_strong = web.filter(
        (pl.col("gateways_detected").list.len() == 1)
        & pl.col("gateway_confidence").is_in(["high", "medium"])
    )
    a_by_v = dict(tier_a.group_by("vertical_label").len().iter_rows())
    return {
        "n": df.height, "n_web": web.height,
        "shopify": shopify.height,
        "shopify_layer": shopify.filter(pl.col("checkout_layer").is_not_null()).height,
        "d2c": d2c.height, "d2c_gokwik": d2c.filter(pl.col("checkout_layer") == "gokwik").height,
        "gw_sites": has_gw.height,
        "razorpay": has_gw.filter(pl.col("gateways_detected").list.contains("razorpay")).height,
        "magic": web.filter(pl.col("checkout_layer") == "razorpay_magic").height,
        "cashfree": has_gw.filter(pl.col("gateways_detected").list.contains("cashfree")).height,
        "single_strong": single_strong.height,
        "saas": saas.height, "saas_intl": saas.filter(pl.col("has_international")).height,
        "saas_intl_sub": saas.filter(pl.col("has_international") & pl.col("has_subscription")).height,
        "edtech": edtech.height,
        "edtech_sub": edtech.filter(pl.col("has_subscription")).height,
        "edtech_gw": edtech.filter(pl.col("gateways_detected").list.len() > 0).height,
        "edtech_app": edtech.filter(pl.col("has_android_app") | pl.col("has_ios_app")).height,
        "a": tier_a.height, "a_d2c": a_by_v.get("D2C", 0), "a_saas": a_by_v.get("SaaS", 0),
        "a_edtech": a_by_v.get("Edtech", 0),
        "a_d2c_layer": tier_a.filter((pl.col("vertical") == "d2c")
                                     & pl.col("checkout_layer").is_not_null()).height,
    }  # fmt: skip


def build() -> None:
    s = stats()
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=INK)
    sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=9, leading=12, textColor=INK_2)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=BLUE,
                        spaceBefore=7, spaceAfter=2)  # fmt: skip
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=9.4, leading=13, textColor=INK)
    small = ParagraphStyle("small", parent=body, fontSize=7.8, leading=10.5, textColor=INK_2)

    story = [
        Paragraph("Where a payments SDR team should focus", h1),
        Spacer(1, 3),
        Paragraph(
            f"Findings from a public-website scan of {s['n']} Indian D2C, edtech and SaaS "
            f"businesses ({s['n_web']} crawled) · Merchant Lead Intelligence Engine · Oct 2026",
            sub,
        ),
        Spacer(1, 6),
    ]

    findings = [
        (
            "1. In D2C, the checkout layer is the battleground, not the gateway",
            f"<b>{pct(s['shopify_layer'], s['shopify'])}</b> of Shopify stores "
            f"({s['shopify_layer']}/{s['shopify']}) run a third-party checkout layer. GoKwik alone "
            f"is on <b>{s['d2c_gokwik']} of {s['d2c']}</b> D2C sites ({pct(s['d2c_gokwik'], s['d2c'])}). "
            "Brands that already pay to improve conversion are the easiest to talk to about payment "
            "success rates behind that checkout.",
        ),
        (
            "2. Where a gateway is visible, it is almost always Razorpay",
            f"A gateway is visible on only {s['gw_sites']} sites (payment scripts usually load at "
            f"the final step). Razorpay appears on <b>{s['razorpay']}</b> of them, {s['magic']} via "
            f"Razorpay Magic Checkout. <b>{s['single_strong']} merchants</b> show a single gateway "
            f"with high or medium confidence, a direct fit for the backup-route pitch. Cashfree is "
            f"visible on {s['cashfree']}.",
        ),
        (
            "3. SaaS selling abroad is the second-best pool",
            f"<b>{pct(s['saas_intl'], s['saas'])}</b> of crawled SaaS companies "
            f"({s['saas_intl']}/{s['saas']}) price for international buyers, and {s['saas_intl_sub']} "
            "of those also sell subscriptions. They need cross-border collections and recurring "
            "billing, not a gateway swap.",
        ),
        (
            "4. Edtech is nearly invisible on the public web",
            f"Only {s['edtech_sub']} of {s['edtech']} edtech sites show subscription pricing and "
            f"{s['edtech_gw']} show a gateway, while {pct(s['edtech_app'], s['edtech'])} push "
            "visitors to an app. Website signals can't qualify this segment. It needs app-store "
            "research and counsellor-led discovery calls.",
        ),
    ]
    for title, text in findings:
        story += [Paragraph(title, h2), Paragraph(text, body)]

    table = Table(
        [
            ["Tier A leads", "D2C", "SaaS", "Edtech", "Total"],
            ["Count", s["a_d2c"], s["a_saas"], s["a_edtech"], s["a"]],
            ["Share", pct(s["a_d2c"], s["a"]), pct(s["a_saas"], s["a"]),
             pct(s["a_edtech"], s["a"]), "100%"],
        ],  # fmt: skip
        colWidths=[34 * mm, 26 * mm, 26 * mm, 26 * mm, 26 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor(INK)),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4fc")),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor(RULE)),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story += [Spacer(1, 8), table]

    layer_note = (
        "every one of them runs GoKwik or Razorpay Magic"
        if s["a_d2c_layer"] == s["a_d2c"]
        else f"{s['a_d2c_layer']} of them run GoKwik or Razorpay Magic"
    )
    story += [
        Paragraph("Recommendation", h2),
        Paragraph(
            f"Put SDR capacity on the <b>{s['a_d2c']} Tier A D2C brands first</b> "
            f"({layer_note}). Lead with a backup route "
            "for sale spikes plus COD-to-prepaid payment links. Then work the "
            f"<b>{s['a_saas']} Tier A SaaS companies</b> on cross-border collections. Don't spend "
            "outbound time on edtech until there's a better data source than the website.",
            body,
        ),
        Spacer(1, 8),
        Paragraph(
            "<b>Limitations.</b> A hand-built sample, not representative of all Indian merchants. "
            "Public pages only, robots.txt respected, and 25 sites blocked the crawler. Gateway "
            "recall is limited because gateways load at the payment step. Funding data is not yet "
            "filled in, so tiers will shift once it is. Scores and openers are generated by "
            "transparent rules in config/icp.yaml.",
            small,
        ),
    ]

    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=14 * mm,
                            title="Insight note: where a payments SDR team should focus")  # fmt: skip
    doc.build(story)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
