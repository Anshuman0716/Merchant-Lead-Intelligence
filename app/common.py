"""Shared data loading, colors, styling and small UI helpers for every page."""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA = Path(__file__).resolve().parent.parent / "exports" / "leads.parquet"

# Page paths (relative to Home.py) used for navigation between pages
OVERVIEW = "views/overview.py"
EXPLORER = "views/lead_explorer.py"
COMPETITORS = "views/competitor_landscape.py"
DETAIL = "views/lead_detail.py"

# Colors: validated reference palette (dataviz skill). Tiers are ordinal -> one blue ramp.
TIER_COLORS = {"A": "#184f95", "B": "#3987e5", "C": "#86b6ef"}
TIER_TEXT = {"A": "#ffffff", "B": "#ffffff", "C": "#0d366b"}
TIER_MEANING = {
    "A": "Call this week",
    "B": "Add to a sequence",
    "C": "Low priority / account manager",
}
VERTICAL_COLORS = {"D2C": "#2a78d6", "Edtech": "#eb6834", "SaaS": "#1baf7a"}
SINGLE = "#2a78d6"
SEQUENTIAL = ["#f3f2ef", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
TEXT, TEXT_2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#ecebe7"
TIERS = ["A", "B", "C"]
VERTICALS = ["D2C", "Edtech", "SaaS"]

LIST_COLS = ["reasons", "suggested_products", "gateways_detected", "gateway_names"]


@st.cache_data
def load_leads() -> pd.DataFrame:
    df = pd.read_parquet(DATA)
    # Missing text values come back as NaN (truthy!); make them None so `if value:` works
    # (columns that are entirely empty, like funding before it's filled in, load as float)
    nullable = ["funding_stage", "last_funding_date", "contact_email", "checkout_layer",
                "checkout_layer_name", "city", "sub_category", "gateway_confidence"]  # fmt: skip
    text_cols = [c for c in df.columns
                 if (pd.api.types.is_string_dtype(df[c]) or df[c].dtype == object
                     or c in nullable) and c not in LIST_COLS]  # fmt: skip
    for c in text_cols:  # note: df.where(cond, None) would put NaN back, so assign explicitly
        df[c] = df[c].astype(object)
        df.loc[df[c].isna(), c] = None
    df["pages_crawled"] = df["pages_crawled"].fillna(0).astype(int)
    for col in LIST_COLS:
        df[col] = df[col].apply(lambda v: list(v) if v is not None else [])
    df["payment_stack"] = df.apply(payment_stack, axis=1)
    df["top_reason"] = df["reasons"].apply(lambda r: r[0] if r else "")
    df["city"] = df["city"].fillna("—")
    return df


def payment_stack(row) -> str:
    parts = list(row["gateway_names"])
    if pd.notna(row.get("checkout_layer_name")):
        parts.append(f"via {row['checkout_layer_name']}")
    return ", ".join(parts) if parts else "Not visible"


# ---------- styling ----------

CSS = """
<style>
  .block-container {padding-top: 1.8rem; padding-bottom: 3rem; max-width: 1320px;}
  [data-testid="stMetricValue"] {font-size: 1.8rem;}
  h3 {margin-top: .4rem;}

  /* Hero banner (Overview) */
  .hero {padding: 26px 30px; border-radius: 16px; margin-bottom: 1.2rem; color: #fff;
         background: linear-gradient(120deg, #0d366b 0%, #184f95 45%, #3987e5 100%);}
  .hero .eyebrow {font-size: .78rem; letter-spacing: .12em; text-transform: uppercase;
                  opacity: .8; font-weight: 600}
  .hero .title {font-size: 2.1rem; font-weight: 700; line-height: 1.2; margin: 4px 0 6px}
  .hero .sub {font-size: 1rem; opacity: .92; max-width: 780px}
  .hero .pills {margin-top: 14px}
  .hero .pill {display: inline-block; padding: 4px 12px; margin: 0 8px 6px 0; border-radius: 999px;
               background: rgba(255,255,255,.16); font-size: .82rem; font-weight: 500}

  /* Page header (other pages) */
  .ph {margin: 0 0 1rem}
  .ph .ph-title {font-size: 1.9rem; font-weight: 700; color: #0b0b0b; line-height: 1.25}
  .ph .ph-sub {color: #52514e; font-size: .98rem; margin-top: 4px; max-width: 900px}

  /* KPI cards */
  .kpi {background: #fff; border: 1px solid #e4e2dd; border-radius: 12px; padding: 14px 16px;
        height: 100%; border-top: 4px solid var(--accent, #2a78d6)}
  .kpi .k-label {color: #52514e; font-size: .85rem; font-weight: 500}
  .kpi .k-value {color: #0b0b0b; font-size: 1.85rem; font-weight: 700; line-height: 1.2;
                 margin-top: 2px}
  .kpi .k-sub {color: #8a8984; font-size: .8rem; margin-top: 2px}

  /* Badges, chips, reasons */
  .tier {display: inline-block; padding: 3px 12px; border-radius: 999px; font-weight: 700;
         font-size: .85rem; letter-spacing: .02em; vertical-align: middle}
  .chip {display: inline-block; padding: 4px 11px; margin: 0 6px 6px 0; border-radius: 999px;
         background: #eef4fc; color: #184f95; font-size: .85rem; border: 1px solid #cde2fb}
  .muted {color: #52514e; font-size: .9rem}
  .reason {padding: 8px 12px; border-left: 3px solid #3987e5; margin-bottom: 8px;
           background: #f7f9fd; border-radius: 0 8px 8px 0}

  /* Lead header card */
  .lead-name {font-size: 1.8rem; font-weight: 700; line-height: 1.2; margin-right: 10px}
  .lead-meta {color: #52514e; font-size: .95rem; margin-top: 6px}
  .lead-meta a {color: #2a78d6; text-decoration: none}

  /* Sidebar */
  .side-brand {font-weight: 700; font-size: 1.05rem; color: #0b0b0b}
  .side-brand span {color: #2a78d6}
  .tier-row {display: flex; align-items: center; gap: 8px; margin: 6px 0; font-size: .85rem;
             color: #52514e}
</style>
"""


def apply_style() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    sub = f'<div class="ph-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(f'<div class="ph"><div class="ph-title">{title}</div>{sub}</div>',
                unsafe_allow_html=True)  # fmt: skip


def kpi(col, label: str, value, sub: str = "", accent: str = SINGLE, help: str = "") -> None:
    """A KPI card with a colored top edge. `help` shows as a hover tooltip."""
    tip = f' title="{html.escape(help)}"' if help else ""
    col.markdown(
        f'<div class="kpi" style="--accent:{accent}"{tip}><div class="k-label">{label}</div>'
        f'<div class="k-value">{value}</div><div class="k-sub">{sub or "&nbsp;"}</div></div>',
        unsafe_allow_html=True,
    )


def tier_badge(tier: str) -> str:
    return (f'<span class="tier" style="background:{TIER_COLORS[tier]};color:{TIER_TEXT[tier]}">'
            f"Tier {tier}</span>")  # fmt: skip


def chips(items: list[str]) -> str:
    return "".join(f'<span class="chip">{html.escape(i)}</span>' for i in items)


def style_fig(fig: go.Figure, height: int = 320, legend: bool = True) -> go.Figure:
    """Recessive axes/grid, readable hover, consistent margins."""
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=36, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_2, size=13),
        title_font=dict(color=TEXT, size=15),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=GRID, font_color=TEXT),
        showlegend=legend,
        legend=dict(
            orientation="h", yanchor="top", y=-0.12, x=0, title_text="", traceorder="normal"
        ),  # fmt: skip
        bargap=0.35,
    )
    axis = dict(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont_color=TEXT_2,
                automargin=True, title_font_color=TEXT_2)  # fmt: skip
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    fig.update_layout(title_x=0, title_xanchor="left")
    return fig


# ---------- navigation and state ----------


def open_lead(domain: str) -> None:
    """Go to the Lead Detail page for this company."""
    st.session_state["nav_domain"] = domain
    st.switch_page(DETAIL)


# Lead Explorer filters: widget key -> default value. Saved in a shadow key so the filters
# survive a trip to another page (Streamlit drops widget state for pages that aren't shown).
FILTER_DEFAULTS = {
    "f_search": "", "f_tier": [], "f_vertical": [], "f_platform": [], "f_gateway": [],
    "f_layer": [], "f_city": [], "f_funding": "Any", "f_sub": False, "f_intl": False,
    "f_email": False, "f_hide_seed": False, "f_min_score": 0, "f_sort": "Score (high → low)",
}  # fmt: skip


def _copy(v):
    return list(v) if isinstance(v, list) else v


def restore_filters() -> None:
    for k, default in FILTER_DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = _copy(st.session_state.get(f"_keep_{k}", default))


def save_filters() -> None:
    for k in FILTER_DEFAULTS:
        st.session_state[f"_keep_{k}"] = _copy(st.session_state[k])


def reset_filters(**overrides) -> None:
    for k, default in FILTER_DEFAULTS.items():
        v = _copy(overrides.get(k, default))
        st.session_state[k] = v
        st.session_state[f"_keep_{k}"] = _copy(v)
