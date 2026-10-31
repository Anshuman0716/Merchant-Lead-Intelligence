"""Shared data loading, colors and small UI helpers for every page."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA = Path(__file__).resolve().parent.parent / "exports" / "leads.parquet"

# Colors: validated reference palette (dataviz skill). Tiers are ordinal -> one blue ramp.
TIER_COLORS = {"A": "#184f95", "B": "#3987e5", "C": "#86b6ef"}
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


def page_setup(title: str, icon: str = "📇") -> None:
    st.set_page_config(page_title=f"{title} · Lead Intelligence", page_icon=icon, layout="wide")
    st.markdown(
        """
        <style>
          .block-container {padding-top: 2rem; max-width: 1280px;}
          [data-testid="stMetricValue"] {font-size: 1.9rem;}
          .tier {display:inline-block; padding:2px 10px; border-radius:999px; color:#fff;
                 font-weight:600; font-size:0.85rem; letter-spacing:.02em}
          .chip {display:inline-block; padding:3px 10px; margin:0 6px 6px 0; border-radius:999px;
                 background:#eef4fc; color:#184f95; font-size:0.85rem; border:1px solid #cde2fb}
          .muted {color:#52514e; font-size:0.9rem}
          .reason {padding:6px 0 6px 12px; border-left:3px solid #3987e5; margin-bottom:8px}
        </style>
        """,
        unsafe_allow_html=True,
    )


def tier_badge(tier: str) -> str:
    return f'<span class="tier" style="background:{TIER_COLORS[tier]}">Tier {tier}</span>'


def chips(items: list[str]) -> str:
    return "".join(f'<span class="chip">{i}</span>' for i in items)


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


def open_lead(domain: str) -> None:
    st.session_state["selected_domain"] = domain
    st.switch_page("pages/3_Lead_Detail.py")
