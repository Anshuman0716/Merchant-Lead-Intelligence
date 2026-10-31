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

pages = {
    "Prospecting": [
        st.Page(OVERVIEW, title="Overview", icon=":material/dashboard:", default=True),
        st.Page(EXPLORER, title="Lead Explorer", icon=":material/manage_search:",
                url_path="Lead_Explorer"),
        st.Page(DETAIL, title="Lead Detail", icon=":material/person_search:",
                url_path="Lead_Detail"),
    ],
    "Market": [
        st.Page(COMPETITORS, title="Competitor Landscape", icon=":material/insights:",
                url_path="Competitor_Landscape"),
    ],
}  # fmt: skip
nav = st.navigation(pages)

df = load_leads()

with st.sidebar:
    st.markdown('<div class="side-brand">📇 Merchant Lead <span>Intelligence</span></div>',
                unsafe_allow_html=True)  # fmt: skip
    st.caption(f"{len(df)} leads · scored {df['scored_at'].max():%d %b %Y}")

    # Quick jump: type any company name to open its brief from any page
    if st.session_state.pop("_clear_jump", False):
        st.session_state["jump"] = None
    names = dict(zip(df["domain"], df["name"], strict=True))
    pick = st.selectbox(
        "Jump to a lead", list(names), index=None, key="jump",
        format_func=lambda d: f"{names[d]}  ·  {d}", placeholder="Type a company name…",
    )  # fmt: skip
    if pick:
        st.session_state["_clear_jump"] = True
        open_lead(pick)

    with st.expander("How tiers work", expanded=False):
        for t, rule in zip(TIERS, ["score ≥ 40", "score 25–39", "score < 25"], strict=True):
            st.markdown(
                f'<div class="tier-row">{tier_badge(t)} <span><b>{rule}</b> · '
                f"{TIER_MEANING[t]}</span></div>",
                unsafe_allow_html=True,
            )
        st.caption("Score = sum of the weights of signals found on the merchant's public pages, "
                   "0–100. Existing Cashfree merchants are always Tier C.")  # fmt: skip

    st.caption("Public pages only · robots.txt respected. Gateway detection is a floor: "
               "most gateways load only at the final payment step.")  # fmt: skip

nav.run()
