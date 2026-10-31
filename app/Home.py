"""Overview: how big is my opportunity?"""

import plotly.graph_objects as go
import streamlit as st
from common import (
    SINGLE,
    TIER_COLORS,
    TIERS,
    VERTICALS,
    load_leads,
    open_lead,
    page_setup,
    style_fig,
)  # fmt: skip

page_setup("Overview")
df = load_leads()
crawled = df[df["data_coverage"] == "website"]

st.title("Merchant Lead Intelligence")
st.markdown(
    '<p class="muted">Which merchants a payments SDR should call first, why, and what to say — '
    f"built from public website signals on {len(df)} Indian D2C, edtech and SaaS businesses. "
    f"Scored {df['scored_at'].max():%d %b %Y}.</p>",
    unsafe_allow_html=True,
)

# ---- KPI tiles ----
n = len(df)
counts = df["tier"].value_counts()
c = st.columns(4)
c[0].metric("Leads scored", n, border=True)
for col, t in zip(c[1:], TIERS, strict=True):
    col.metric(f"Tier {t}", int(counts.get(t, 0)), f"{counts.get(t, 0) / n:.0%} of leads",
               delta_color="off", delta_arrow="off", border=True)  # fmt: skip


def share(mask) -> str:
    return f"{mask.mean():.0%}"


strong_gw = crawled["gateway_confidence"].isin(["high", "medium"])
c = st.columns(4)
c[0].metric("Gateway visible", share(strong_gw), "high/medium confidence", delta_color="off", delta_arrow="off",
            border=True, help="Gateways usually load only at the final payment step, so this is a floor.")  # fmt: skip
c[1].metric("Use a checkout layer", share(crawled["checkout_layer"].notna()),
            "GoKwik, Razorpay Magic, Shopflo…", delta_color="off", delta_arrow="off", border=True)  # fmt: skip
c[2].metric(
    "Sell subscriptions",
    share(crawled["has_subscription"]),
    delta_color="off",
    delta_arrow="off",
    border=True,
)
c[3].metric("Sell internationally", share(crawled["has_international"]), delta_color="off", delta_arrow="off",
            border=True)  # fmt: skip

# ---- Charts ----
left, right = st.columns([1.1, 1])
with left:
    tv = df.groupby(["vertical_label", "tier"]).size().unstack(fill_value=0)
    fig = go.Figure()
    for t in TIERS:
        fig.add_bar(
            y=VERTICALS, x=[int(tv.loc[v, t]) if v in tv.index and t in tv else 0 for v in VERTICALS],
            name=f"Tier {t}", orientation="h", marker_color=TIER_COLORS[t],
            marker_line=dict(color="#fcfcfb", width=2),
            hovertemplate="%{y} · Tier " + t + ": <b>%{x}</b> leads<extra></extra>",
        )  # fmt: skip
    fig.update_layout(barmode="stack", title="Leads by vertical and tier")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(style_fig(fig), use_container_width=True, theme=None)

with right:
    fig = go.Figure(
        go.Histogram(
            x=df["score"], xbins=dict(start=0, end=105, size=5), marker_color=SINGLE,
            marker_line=dict(color="#fcfcfb", width=2),
            hovertemplate="Score %{x}: <b>%{y}</b> leads<extra></extra>",
        )
    )  # fmt: skip
    for thr, label in [(25, "Tier B ≥ 25"), (40, "Tier A ≥ 40")]:
        fig.add_vline(x=thr, line=dict(color="#52514e", width=1, dash="dot"),
                      annotation_text=label, annotation_position="top right",
                      annotation_font_color="#52514e")  # fmt: skip
    fig.update_layout(title="Score distribution")
    fig.update_xaxes(title="ICP score (0–100)")
    fig.update_yaxes(title="Leads")
    st.plotly_chart(style_fig(fig, legend=False), use_container_width=True, theme=None)

# ---- Call first ----
st.subheader("Call these first")
st.caption("Top Tier A leads. Select a row to open the full lead brief.")
top = df[df["tier"] == "A"].head(10)
event = st.dataframe(
    top[["name", "vertical_label", "score", "top_reason", "opener"]],
    hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
    column_config={
        "name": "Company", "vertical_label": "Vertical",
        "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
        "top_reason": st.column_config.TextColumn("Why call", width="large"),
        "opener": st.column_config.TextColumn("Suggested opener", width="large"),
    },
)  # fmt: skip
if event.selection.rows:
    open_lead(top.iloc[event.selection.rows[0]]["domain"])

st.markdown(
    '<p class="muted">Data: public pages only, robots.txt respected. Gateway detection has '
    "limited recall because payment scripts usually load only at the final payment step.</p>",
    unsafe_allow_html=True,
)
