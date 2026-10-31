"""Overview: how big is my opportunity, and who do I call first?"""

import plotly.graph_objects as go
import streamlit as st
from common import (
    COMPETITORS,
    EXPLORER,
    SINGLE,
    TIER_COLORS,
    TIER_MEANING,
    TIERS,
    VERTICALS,
    kpi,
    load_leads,
    open_lead,
    reset_filters,
    style_fig,
)

df = load_leads()
crawled = df[df["data_coverage"] == "website"]
n = len(df)
counts = df["tier"].value_counts()

st.markdown(
    f"""<div class="hero">
      <div class="eyebrow">Payments SDR workspace</div>
      <div class="title">Merchant Lead Intelligence</div>
      <div class="sub">Which merchants to call first, why, and what to say — built from public
        website signals on {n} Indian D2C, edtech and SaaS businesses.</div>
      <div class="pills">
        <span class="pill">{int(counts.get("A", 0))} Tier A leads ready to call</span>
        <span class="pill">{len(crawled)} websites analysed</span>
        <span class="pill">Scored {df["scored_at"].max():%d %b %Y}</span>
      </div>
    </div>""",
    unsafe_allow_html=True,
)

# ---- Quick actions ----
a = st.columns(3)
if a[0].button("📞  Open today's Tier A call list", type="primary", use_container_width=True):
    reset_filters(f_tier=["A"])
    st.switch_page(EXPLORER)
if a[1].button("🎯  Brief for the #1 lead", use_container_width=True):
    open_lead(df.iloc[0]["domain"])
if a[2].button("🧭  See who we're competing with", use_container_width=True):
    st.switch_page(COMPETITORS)

# ---- Lead KPIs ----
st.markdown("### Pipeline")
c = st.columns(4)
kpi(c[0], "Leads scored", n, "D2C · Edtech · SaaS", accent="#52514e")
for col, t in zip(c[1:], TIERS, strict=True):
    k = int(counts.get(t, 0))
    kpi(col, f"Tier {t}", k, f"{k / n:.0%} of leads · {TIER_MEANING[t].lower()}",
        accent=TIER_COLORS[t])  # fmt: skip


# ---- Payment stack KPIs ----
def share(mask) -> str:
    return f"{mask.mean():.0%}" if len(mask) else "—"


st.markdown("### Payment stack seen on public pages")
strong_gw = crawled["gateway_confidence"].isin(["high", "medium"])
c = st.columns(4)
kpi(c[0], "Gateway visible", share(strong_gw), "high/medium confidence — a floor",
    help="Gateways usually load only at the final payment step, so this is a minimum.")  # fmt: skip
kpi(c[1], "Use a checkout layer", share(crawled["checkout_layer"].notna()),
    "GoKwik, Razorpay Magic, Shopflo…")  # fmt: skip
kpi(c[2], "Sell subscriptions", share(crawled["has_subscription"].fillna(False).astype(bool)),
    "recurring plans or renewals")  # fmt: skip
kpi(c[3], "Sell internationally", share(crawled["has_international"].fillna(False).astype(bool)),
    "overseas shipping or USD pricing")  # fmt: skip

st.write("")

# ---- Charts ----
left, right = st.columns([1.1, 1])
with left, st.container(border=True):
    tv = df.groupby(["vertical_label", "tier"]).size().unstack(fill_value=0)
    fig = go.Figure()
    for t in TIERS:
        fig.add_bar(
            y=VERTICALS, x=[int(tv.loc[v, t]) if v in tv.index and t in tv else 0 for v in VERTICALS],
            name=f"Tier {t}", orientation="h", marker_color=TIER_COLORS[t],
            marker_line=dict(color="#ffffff", width=2),
            hovertemplate="%{y} · Tier " + t + ": <b>%{x}</b> leads<extra></extra>",
        )  # fmt: skip
    fig.update_layout(barmode="stack", title="Leads by vertical and tier")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(style_fig(fig), use_container_width=True, theme=None)

with right, st.container(border=True):
    fig = go.Figure(
        go.Histogram(
            x=df["score"], xbins=dict(start=0, end=105, size=5), marker_color=SINGLE,
            marker_line=dict(color="#ffffff", width=2),
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
st.markdown("### Call these first")
vert = st.segmented_control("Vertical", ["All", *VERTICALS], default="All", key="ov_vertical",
                            label_visibility="collapsed")  # fmt: skip
top = df[df["tier"] == "A"]
if vert and vert != "All":
    top = top[top["vertical_label"] == vert]
top = top.head(10)
st.caption("Top Tier A leads by score. **Click a row** to open its full call brief.")
if top.empty:
    st.info("No Tier A leads in this vertical yet — try Tier B in the Lead Explorer.")
else:
    event = st.dataframe(
        top[["name", "vertical_label", "score", "top_reason", "opener"]],
        hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
        key=f"top_table_{vert}",
        column_config={
            "name": st.column_config.TextColumn("Company", pinned=True),
            "vertical_label": "Vertical",
            "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
            "top_reason": st.column_config.TextColumn("Why call", width="large"),
            "opener": st.column_config.TextColumn("Suggested opener", width="large"),
        },
    )  # fmt: skip
    if event.selection.rows:
        open_lead(top.iloc[event.selection.rows[0]]["domain"])
