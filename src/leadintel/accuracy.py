"""Detection accuracy check against a hand-labelled sample.

    python -m leadintel.accuracy sample      # writes docs/accuracy/labels.csv (40 random sites)
    python -m leadintel.accuracy score       # compares labels to signals, writes results.md

How to label: open each site in Chrome, check DevTools (Network + Sources) on the home,
product and cart pages, and fill:
    true_platform        shopify / woocommerce / magento / custom
    true_gateways        e.g. "razorpay" or "razorpay;payu"; "none" if you looked and found none;
                         leave blank / "unknown" if you can't tell (excluded from recall)
    true_checkout_layer  gokwik / shiprocket / razorpay_magic / shopflo / chargebee / none
Detected values are deliberately NOT in the sheet, so labelling isn't biased by them.
"""

from __future__ import annotations

import sys
from collections import Counter

import polars as pl

from leadintel.db import get_conn, read_table
from leadintel.settings import ROOT

OUT_DIR = ROOT / "docs" / "accuracy"
LABELS = OUT_DIR / "labels.csv"
RESULTS = OUT_DIR / "results.md"
SAMPLE_SIZE = 40
SEED = 7


def sample() -> None:
    if LABELS.exists():
        sys.exit(f"{LABELS} already exists; delete it first if you want a new sample.")
    with get_conn() as conn:
        companies = read_table("companies", conn)
        signals = read_table("signals", conn).filter(pl.col("pages_crawled") > 0)
    df = (
        companies.join(signals.select("domain"), on="domain")
        .sample(SAMPLE_SIZE, seed=SEED)
        .select("domain", "name", "vertical", "homepage_url")
        .with_columns(
            true_platform=pl.lit(""),
            true_gateways=pl.lit(""),
            true_checkout_layer=pl.lit(""),
            notes=pl.lit(""),
        )  # fmt: skip
        .sort("vertical", "domain")
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.write_csv(LABELS)
    print(f"Wrote {df.height} rows to {LABELS}")


def _split(v: str | None) -> set[str] | None:
    """'' / 'unknown' -> None (not labelled); 'none' -> empty set."""
    v = (v or "").strip().lower()
    if v in ("", "unknown", "?"):
        return None
    if v == "none":
        return set()
    return {x.strip() for x in v.replace(",", ";").split(";") if x.strip()}


def _pr(tp: int, fp: int, fn: int) -> tuple[str, str]:
    p = f"{tp / (tp + fp):.0%}" if tp + fp else "n/a"
    r = f"{tp / (tp + fn):.0%}" if tp + fn else "n/a"
    return p, r


def score() -> None:
    labels = pl.read_csv(LABELS, infer_schema=False).fill_null("")
    with get_conn() as conn:
        signals = read_table("signals", conn)
    df = labels.join(signals, on="domain", how="left")

    lines = ["# Detection accuracy", "", f"Hand-labelled sample: {df.height} sites.", ""]

    # Platform: accuracy + per-class precision/recall
    plat = df.filter(pl.col("true_platform").str.strip_chars() != "")
    pairs = [
        (t.strip().lower(), p) for t, p in zip(plat["true_platform"], plat["platform"], strict=True)
    ]
    correct = sum(t == p for t, p in pairs)
    lines += [f"## Platform ({len(pairs)} labelled)", "",
              f"Overall accuracy: **{correct / max(len(pairs), 1):.0%}**", "",
              "| Platform | Precision | Recall | Support |", "|---|---|---|---|"]  # fmt: skip
    for cls in sorted({t for t, _ in pairs} | {p for _, p in pairs}):
        tp = sum(t == cls and p == cls for t, p in pairs)
        fp = sum(t != cls and p == cls for t, p in pairs)
        fn = sum(t == cls and p != cls for t, p in pairs)
        p_, r_ = _pr(tp, fp, fn)
        lines.append(f"| {cls} | {p_} | {r_} | {tp + fn} |")

    # Gateways: (company, gateway) pairs
    tp = fp = fn = 0
    per_gw: Counter = Counter()
    misses = []
    for row in df.iter_rows(named=True):
        truth = _split(row["true_gateways"])
        pred = set(row["gateways_detected"] or [])
        if truth is None:
            continue
        tp += len(truth & pred)
        fp += len(pred - truth)
        fn += len(truth - pred)
        for g in truth & pred:
            per_gw[(g, "tp")] += 1
        for g in pred - truth:
            per_gw[(g, "fp")] += 1
            misses.append(
                f"- {row['domain']}: detected `{g}` but label says {sorted(truth) or 'none'}"
            )
        for g in truth - pred:
            per_gw[(g, "fn")] += 1
            misses.append(f"- {row['domain']}: missed `{g}`")
    p_, r_ = _pr(tp, fp, fn)
    lines += ["", "## Payment gateway", "", f"Precision **{p_}**, recall **{r_}** "
              f"(TP={tp}, FP={fp}, FN={fn}; sites labelled 'unknown' excluded).", "",
              "| Gateway | Precision | Recall |", "|---|---|---|"]  # fmt: skip
    for g in sorted({g for g, _ in per_gw}):
        gp, gr = _pr(per_gw[(g, "tp")], per_gw[(g, "fp")], per_gw[(g, "fn")])
        lines.append(f"| {g} | {gp} | {gr} |")

    # Checkout layer: exact match accuracy
    co = df.filter(pl.col("true_checkout_layer").str.strip_chars() != "")
    co_ok = sum(
        (t.strip().lower() or "none") == (p or "none")
        for t, p in zip(co["true_checkout_layer"], co["checkout_layer"], strict=True)
    )
    lines += ["", f"## Checkout layer ({co.height} labelled)", "",
              f"Exact-match accuracy: **{co_ok / max(co.height, 1):.0%}**", ""]  # fmt: skip
    if misses:
        lines += ["## Gateway errors to review", "", *misses, ""]

    RESULTS.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"sample": sample, "score": score}.get(cmd, lambda: sys.exit(__doc__))()
