"""Shared data loading, colors, styling and small UI helpers for every page."""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "exports" / "leads.parquet"
COMPETITORS_YAML = ROOT / "config" / "competitors.yaml"
ICP_YAML = ROOT / "config" / "icp.yaml"
CALL_LOG = ROOT / "data" / "sdr" / "call_log.csv"

# Page paths (relative to Home.py) used for navigation between pages
OVERVIEW = "views/overview.py"
EXPLORER = "views/lead_explorer.py"
COMPETITORS = "views/competitor_landscape.py"
DETAIL = "views/lead_detail.py"

# ---------- palette (light theme, indigo primary) ----------
INK, INK_2, MUTED = "#0f172a", "#334155", "#64748b"
BORDER, GRID, SURFACE, BG = "#e2e8f0", "#edf0f5", "#ffffff", "#f5f7fb"
PRIMARY, PRIMARY_DARK, PRIMARY_SOFT = "#4f46e5", "#312e81", "#eef2ff"
GOOD, WARN, BAD = "#059669", "#d97706", "#e11d48"

# Tiers are ordinal -> one indigo ramp, darkest = best
TIER_COLORS = {"A": "#3730a3", "B": "#6366f1", "C": "#c7d2fe"}
TIER_TEXT = {"A": "#ffffff", "B": "#ffffff", "C": "#312e81"}
TIER_MEANING = {"A": "Call this week", "B": "Add to a sequence", "C": "Low priority"}
VERTICAL_COLORS = {"D2C": "#4f46e5", "Edtech": "#f59e0b", "SaaS": "#10b981"}
SINGLE = PRIMARY
SEQUENTIAL = ["#f5f7fb", "#e0e7ff", "#a5b4fc", "#6366f1", "#4338ca", "#312e81"]
TEXT, TEXT_2 = INK, INK_2
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


@st.cache_data
def load_competitors() -> dict:
    return yaml.safe_load(COMPETITORS_YAML.read_text(encoding="utf-8"))


@st.cache_data
def load_icps() -> dict:
    return yaml.safe_load(ICP_YAML.read_text(encoding="utf-8"))["icps"]


def payment_stack(row) -> str:
    parts = list(row["gateway_names"])
    if pd.notna(row.get("checkout_layer_name")):
        parts.append(f"via {row['checkout_layer_name']}")
    return ", ".join(parts) if parts else "Not visible"


# ---------- SDR call log (a CSV on disk, one row per logged call) ----------

LOG_COLS = ["logged_at", "domain", "company", "sdr", "outcome", "budget_status", "budget_notes",
            "authority_status", "authority_notes", "need_status", "need_notes",
            "timeline_status", "timeline_notes", "next_step", "follow_up", "notes"]  # fmt: skip


def read_call_log() -> pd.DataFrame:
    if not CALL_LOG.exists():
        return pd.DataFrame(columns=LOG_COLS)
    log = pd.read_csv(CALL_LOG, dtype=str, keep_default_na=False)
    return log.reindex(columns=LOG_COLS, fill_value="")


def append_call_log(entry: dict) -> None:
    CALL_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {c: str(entry.get(c, "") or "") for c in LOG_COLS}
    row["logged_at"] = row["logged_at"] or datetime.now().strftime("%Y-%m-%d %H:%M")
    pd.DataFrame([row]).to_csv(CALL_LOG, mode="a", header=not CALL_LOG.exists(), index=False)


def last_outcomes() -> dict[str, str]:
    """domain -> most recent call outcome, for the 'last call' badge on lead cards."""
    log = read_call_log()
    if log.empty:
        return {}
    return log.sort_values("logged_at").groupby("domain")["outcome"].last().to_dict()


# ---------- styling ----------

CSS = """
<style>
  .block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1280px;}
  h1, h2, h3, h4 {color: #0f172a; letter-spacing: -.01em;}
  .stButton button p, .stDownloadButton button p, .stLinkButton a p {font-weight: 600;}
  [data-testid="stVerticalBlockBorderWrapper"] {border-radius: 14px;}
  [data-testid="stExpander"] details {border-radius: 12px;}
  div[data-testid="stTabs"] button p {font-weight: 600; font-size: .95rem;}

  /* Hero banner (Overview) */
  .hero {padding: 28px 32px 26px; border-radius: 18px; margin-bottom: 1.1rem; color: #fff;
         background: linear-gradient(120deg, #1e1b4b 0%, #312e81 40%, #4f46e5 100%);
         box-shadow: 0 10px 30px -12px rgba(49,46,129,.55);}
  .hero .eyebrow {font-size: .76rem; letter-spacing: .14em; text-transform: uppercase;
                  color: #c7d2fe; font-weight: 700}
  .hero .title {font-size: 2.15rem; font-weight: 800; line-height: 1.15; margin: 6px 0 10px}
  .hero .line {height: 3px; width: 72px; border-radius: 3px; margin: 0 0 12px;
               background: linear-gradient(90deg, #a5b4fc, #5eead4);}
  .hero .sub {font-size: 1.02rem; color: #e0e7ff; max-width: 820px; line-height: 1.5}

  /* Page header and section headers: solid title + accent line */
  .ph {margin: 0 0 1.1rem}
  .ph .ph-title {font-size: 2rem; font-weight: 800; color: #0f172a; line-height: 1.2}
  .ph .ph-line {height: 3px; width: 64px; border-radius: 3px; margin: 8px 0 10px;
                background: linear-gradient(90deg, #4f46e5, #14b8a6);}
  .ph .ph-sub {color: #475569; font-size: .98rem; max-width: 900px}
  .sec {margin: 1.6rem 0 .8rem; padding-bottom: 8px; border-bottom: 1px solid #e2e8f0;
        display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap}
  .sec .sec-title {font-size: 1.3rem; font-weight: 800; color: #0f172a;
                   padding-left: 12px; border-left: 4px solid #4f46e5; line-height: 1.2}
  .sec .sec-sub {color: #64748b; font-size: .9rem}

  /* KPI grid: equal-height cards that always line up */
  .kpis {display: grid; grid-template-columns: repeat(var(--n, 4), minmax(0, 1fr)); gap: 14px;
         margin-bottom: 14px}
  @media (max-width: 900px) {.kpis {grid-template-columns: repeat(2, minmax(0, 1fr));}}
  .kpi {background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 16px 18px;
        position: relative; overflow: hidden; display: flex; flex-direction: column;
        box-shadow: 0 1px 2px rgba(15,23,42,.04)}
  .kpi::before {content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
                background: var(--accent, #4f46e5)}
  .kpi .k-label {color: #475569; font-size: .8rem; font-weight: 700; text-transform: uppercase;
                 letter-spacing: .05em}
  .kpi .k-value {color: #0f172a; font-size: 2rem; font-weight: 800; line-height: 1.15;
                 margin-top: 6px}
  .kpi .k-sub {color: #64748b; font-size: .82rem; margin-top: auto; padding-top: 4px}

  /* Badges, chips, bars */
  .tier {display: inline-block; padding: 3px 11px; border-radius: 999px; font-weight: 700;
         font-size: .8rem; letter-spacing: .02em; vertical-align: middle; white-space: nowrap}
  .chip {display: inline-block; padding: 3px 10px; margin: 0 6px 6px 0; border-radius: 999px;
         background: #eef2ff; color: #3730a3; font-size: .8rem; font-weight: 600;
         border: 1px solid #e0e7ff; white-space: nowrap}
  .chip.v-D2C {background:#eef2ff; color:#3730a3; border-color:#e0e7ff}
  .chip.v-Edtech {background:#fffbeb; color:#92400e; border-color:#fde68a}
  .chip.v-SaaS {background:#ecfdf5; color:#065f46; border-color:#a7f3d0}
  .chip.log {background:#f0fdfa; color:#115e59; border-color:#99f6e4}
  .muted {color: #64748b; font-size: .88rem}
  .sbar {white-space: nowrap}
  .bar {display: inline-block; width: 64px; height: 8px; border-radius: 99px;
        background: #e2e8f0; vertical-align: middle; overflow: hidden; margin-right: 8px}
  .bar > span {display: block; height: 100%; border-radius: 99px;
               background: linear-gradient(90deg, #6366f1, #3730a3)}
  .score {font-weight: 800; color: #0f172a; font-size: .95rem; vertical-align: middle}

  /* Lead rows (Overview + Explorer) */
  .rank {width: 34px; height: 34px; border-radius: 10px; background: #eef2ff; color: #3730a3;
         font-weight: 800; display: flex; align-items: center; justify-content: center}
  .lr-name {font-weight: 800; font-size: 1.05rem; color: #0f172a; margin-right: 8px}
  .lr-meta {color: #64748b; font-size: .84rem; margin-top: 4px}
  .lr-label {color: #64748b; font-size: .72rem; font-weight: 700; text-transform: uppercase;
             letter-spacing: .06em}
  .lr-why {color: #0f172a; font-size: .92rem; font-weight: 600; margin-top: 2px}
  .lr-open {color: #475569; font-size: .86rem; font-style: italic; margin-top: 4px}

  /* Lead detail */
  .profile {display: flex; justify-content: space-between; gap: 24px; flex-wrap: wrap;
            align-items: flex-start}
  .lead-name {font-size: 2rem; font-weight: 800; line-height: 1.15; margin-right: 10px;
              color: #0f172a}
  .lead-sub {color: #475569; font-size: .92rem; margin-top: 6px}
  .facts {display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px 20px;
          margin-top: 18px; padding-top: 16px; border-top: 1px solid #e2e8f0}
  @media (max-width: 900px) {.facts {grid-template-columns: repeat(2, minmax(0, 1fr));}}
  .fact .f-label {color: #64748b; font-size: .72rem; font-weight: 700; text-transform: uppercase;
                  letter-spacing: .06em}
  .fact .f-value {color: #0f172a; font-size: .95rem; font-weight: 600; margin-top: 2px;
                  word-break: break-word}
  .fact a {color: #4f46e5; text-decoration: none}
  .scorebox {text-align: center; min-width: 120px; padding: 10px 18px; border-radius: 14px;
             background: #eef2ff; border: 1px solid #e0e7ff}
  .scorebox .s-num {font-size: 2.4rem; font-weight: 800; color: #312e81; line-height: 1}
  .scorebox .s-label {font-size: .72rem; color: #475569; font-weight: 700;
                      text-transform: uppercase; letter-spacing: .06em; margin-top: 4px}
  .why {margin: 0; padding: 0; list-style: none}
  .why li {position: relative; padding: 10px 12px 10px 40px; margin-bottom: 8px;
           background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px;
           font-weight: 600; color: #0f172a; font-size: .93rem}
  .why li::before {content: counter(item); counter-increment: item; position: absolute;
                   left: 10px; top: 9px; width: 22px; height: 22px; border-radius: 7px;
                   background: #4f46e5; color: #fff; font-size: .75rem; font-weight: 800;
                   display: flex; align-items: center; justify-content: center}
  .why {counter-reset: item}
  .contact-row {display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px dashed #e2e8f0;
                font-size: .92rem}
  .contact-row:last-child {border-bottom: 0}
  .contact-row .c-label {color: #64748b; width: 110px; flex-shrink: 0; font-weight: 600}
  .contact-row .c-value {color: #0f172a; font-weight: 600; word-break: break-word}
  .contact-row a {color: #4f46e5; text-decoration: none}
  .opener {padding: 16px 20px; border-radius: 12px; background: #f8fafc;
           border: 1px solid #e2e8f0; border-left: 4px solid #4f46e5; color: #0f172a;
           font-size: 1.02rem; line-height: 1.55; font-weight: 500}
  .bant-head {display: flex; align-items: center; gap: 8px; font-weight: 800; color: #0f172a}
  .bant-ico {width: 30px; height: 30px; border-radius: 9px; display: flex; align-items: center;
             justify-content: center; font-size: 1rem; background: #eef2ff}
  .bant-guess {color: #334155; font-size: .88rem; margin: 8px 0 4px; min-height: 3.6em}
  .bant-tag {color: #64748b; font-size: .7rem; font-weight: 700; text-transform: uppercase;
             letter-spacing: .06em; margin-top: 6px}

  /* Battlecards */
  .bc-head {display: flex; align-items: center; gap: 10px; flex-wrap: wrap}
  .bc-name {font-size: 1.5rem; font-weight: 800; color: #0f172a}
  .threat {padding: 3px 10px; border-radius: 999px; font-size: .75rem; font-weight: 700}
  .bc-list {margin: 4px 0 0; padding-left: 18px; color: #0f172a; font-size: .9rem}
  .bc-list li {margin-bottom: 4px}
  .bc-title {font-weight: 800; font-size: .95rem; margin-bottom: 4px}

  /* Sidebar */
  section[data-testid="stSidebar"] {border-right: 1px solid #e2e8f0}
  .side-brand {font-weight: 800; font-size: 1.2rem; color: #0f172a; line-height: 1.25}
  .side-brand span {color: #4f46e5}
  .side-meta {color: #64748b; font-size: .8rem; margin-top: 2px}
  .side-sec {color: #64748b; font-size: .72rem; font-weight: 800; letter-spacing: .1em;
             text-transform: uppercase; margin: 18px 0 4px}
  .tier-row {display: flex; align-items: center; gap: 8px; margin: 6px 0; font-size: .85rem;
             color: #334155}
</style>
"""


def apply_style() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    sub = f'<div class="ph-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(f'<div class="ph"><div class="ph-title">{title}</div><div class="ph-line"></div>'
                f"{sub}</div>", unsafe_allow_html=True)  # fmt: skip


def section(title: str, subtitle: str = "") -> None:
    sub = f'<div class="sec-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(f'<div class="sec"><div class="sec-title">{title}</div>{sub}</div>',
                unsafe_allow_html=True)  # fmt: skip


def kpi_row(items: list[tuple]) -> None:
    """Equal-height KPI cards in one grid. items: (label, value, sub, accent[, help])."""
    cards = []
    for it in items:
        label, value, sub, accent = it[:4]
        tip = f' title="{html.escape(it[4])}"' if len(it) > 4 else ""
        cards.append(f'<div class="kpi" style="--accent:{accent}"{tip}>'
                     f'<div class="k-label">{label}</div><div class="k-value">{value}</div>'
                     f'<div class="k-sub">{sub or "&nbsp;"}</div></div>')  # fmt: skip
    st.markdown(f'<div class="kpis" style="--n:{len(items)}">{"".join(cards)}</div>',
                unsafe_allow_html=True)  # fmt: skip


def tier_badge(tier: str) -> str:
    return (f'<span class="tier" style="background:{TIER_COLORS[tier]};color:{TIER_TEXT[tier]}">'
            f"Tier {tier}</span>")  # fmt: skip


def chips(items: list[str], cls: str = "") -> str:
    return "".join(f'<span class="chip {cls}">{html.escape(i)}</span>' for i in items)


def vertical_chip(v: str) -> str:
    return f'<span class="chip v-{v}">{html.escape(v)}</span>'


def score_bar(score) -> str:
    s = int(score)
    return f'<span class="sbar"><span class="bar"><span style="width:{s}%"></span></span><span class="score">{s}</span></span>'


def style_fig(fig: go.Figure, height: int = 320, legend: bool = True) -> go.Figure:
    """Recessive axes/grid, readable hover, consistent margins."""
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=40, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=INK_2, size=13),
        title_font=dict(color=INK, size=15, weight=700),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=BORDER, font_color=INK),
        showlegend=legend,
        legend=dict(
            orientation="h", yanchor="top", y=-0.12, x=0, title_text="", traceorder="normal"
        ),  # fmt: skip
        bargap=0.35,
    )
    axis = dict(gridcolor=GRID, zeroline=False, linecolor=BORDER, tickfont_color=INK_2,
                automargin=True, title_font_color=INK_2)  # fmt: skip
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    fig.update_layout(title_x=0, title_xanchor="left")
    return fig


def hbar(counts: pd.Series, title: str, total: int, color: str = PRIMARY) -> go.Figure:
    """Horizontal bar of counts with 'n (x%)' labels, biggest on top."""
    counts = counts.sort_values()
    fig = go.Figure(
        go.Bar(
            x=counts.values, y=counts.index, orientation="h", marker_color=color,
            marker_cornerradius=5, text=[f"{v} ({v / total:.0%})" for v in counts.values],
            textposition="outside", textfont_color=INK_2, cliponaxis=False,
            hovertemplate="%{y}: <b>%{x}</b> merchants<extra></extra>",
        )
    )  # fmt: skip
    fig.update_layout(title=title)
    fig.update_xaxes(showgrid=False, showticklabels=False,
                     range=[0, (counts.max() if len(counts) else 1) * 1.35])  # fmt: skip
    fig.update_yaxes(showgrid=False)
    return style_fig(fig, height=max(170, 80 + 34 * len(counts)), legend=False)


# ---------- lead rows (replace wide tables: no sideways scrolling) ----------


def lead_row(lead, rank: int, key: str, opener: bool = True, last_call: str = "") -> None:
    """One lead as a bordered row: rank · company · why call (+ opener) · score · open button."""
    with st.container(border=True):
        c = st.columns([0.45, 2.9, 4.3, 1.5, 1.2], vertical_alignment="center", gap="small")
        c[0].markdown(f'<div class="rank">{rank}</div>', unsafe_allow_html=True)
        meta = [lead["platform_label"], lead["city"] if lead["city"] != "—" else None]
        logged = (
            f' <span class="chip log">Last call: {html.escape(last_call)}</span>'
            if last_call
            else ""
        )
        c[1].markdown(
            f'<span class="lr-name">{html.escape(lead["name"])}</span>{tier_badge(lead["tier"])}'
            f'<div class="lr-meta">{vertical_chip(lead["vertical_label"])}'
            + " · ".join(html.escape(str(m)) for m in meta if m)
            + f"{logged}</div>",
            unsafe_allow_html=True,
        )
        body = (f'<div class="lr-label">Why call</div>'
                f'<div class="lr-why">{html.escape(lead["top_reason"] or "—")}</div>')  # fmt: skip
        if opener:
            body += f'<div class="lr-open">“{html.escape(lead["opener"])}”</div>'
        else:
            body += (
                f'<div class="lr-meta">Payment stack: {html.escape(lead["payment_stack"])}</div>'
            )
        c[2].markdown(body, unsafe_allow_html=True)
        c[3].markdown(f'<div class="lr-label">Score</div>{score_bar(lead["score"])}',
                      unsafe_allow_html=True)  # fmt: skip
        if c[4].button("Open", key=f"{key}_{lead['domain']}", type="primary",
                       use_container_width=True):  # fmt: skip
            open_lead(lead["domain"])


# ---------- navigation and state ----------


def open_lead(domain: str) -> None:
    """Go to the Lead Detail page for this company."""
    st.session_state["nav_domain"] = domain
    st.switch_page(DETAIL)


# Lead Explorer filters: widget key -> default value. Saved in a shadow key so the filters
# survive a trip to another page (Streamlit drops widget state for pages that aren't shown).
FILTER_DEFAULTS = {
    "f_search": None, "f_tier": [], "f_vertical": [], "f_platform": [], "f_gateway": [],
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
    st.session_state["ex_page"] = 1
