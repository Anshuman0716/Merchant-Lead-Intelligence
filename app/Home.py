"""App entry point: page config, shared styling, sidebar and navigation.

Run with:  uv run streamlit run app/Home.py
"""

import streamlit as st
from common import (
    COMPETITORS,
    DETAIL,
    EXPLORER,
    OVERVIEW,
    TIER_MEANING,
    TIERS,
    apply_style,
    load_leads,
    open_lead,
    tier_badge,
)

st.set_page_config(page_title="Lead Intelligence", page_icon="📇", layout="wide")
apply_style()

overview = st.Page(OVERVIEW, title="Overview", icon=":material/dashboard:", default=True)
explorer = st.Page(EXPLORER, title="Lead Explorer", icon=":material/manage_search:",
                   url_path="Lead_Explorer")  # fmt: skip
detail = st.Page(DETAIL, title="Lead Detail", icon=":material/person_search:",
                 url_path="Lead_Detail")  # fmt: skip
competitors = st.Page(COMPETITORS, title="Competitor Landscape", icon=":material/insights:",
                      url_path="Competitor_Landscape")  # fmt: skip

# The menu is drawn by hand below so the sidebar can have its own heading and sections
nav = st.navigation([overview, explorer, detail, competitors], position="hidden")

df = load_leads()

with st.sidebar:
    st.markdown(
        '<div class="side-brand">📇 Merchant Lead <span>Intelligence</span></div>'
        f'<div class="side-meta">{len(df):,} leads · scored {df["scored_at"].max():%d %b %Y}</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="side-sec">Prospecting</div>', unsafe_allow_html=True)
    st.page_link(overview)
    st.page_link(explorer)
    st.page_link(detail)

    st.markdown('<div class="side-sec">Market</div>', unsafe_allow_html=True)
    st.page_link(competitors)

    st.markdown('<div class="side-sec">Search for a company</div>', unsafe_allow_html=True)
    if st.session_state.pop("_clear_jump", False):
        st.session_state["jump"] = None
    names = dict(zip(df["domain"], df["name"], strict=True))
    by_name = sorted(names, key=lambda d: names[d].lower())
    pick = st.selectbox(
        "Search for a company", by_name, index=None, key="jump", label_visibility="collapsed",
        format_func=lambda d: f"{names[d]}  ·  {d}", placeholder="Type a company name…",
    )  # fmt: skip
    if pick:
        st.session_state["_clear_jump"] = True
        open_lead(pick)

    st.markdown('<div class="side-sec">How tiers work</div>', unsafe_allow_html=True)
    for t, rule in zip(TIERS, ["score ≥ 40", "score 25–39", "score < 25"], strict=True):
        st.markdown(
            f'<div class="tier-row">{tier_badge(t)} <span><b>{rule}</b> · '
            f"{TIER_MEANING[t]}</span></div>",
            unsafe_allow_html=True,
        )
    st.caption("Score = sum of the weights of signals found on the merchant's public pages "
               "(0–100). Existing Cashfree merchants are always Tier C.")  # fmt: skip

nav.run()
