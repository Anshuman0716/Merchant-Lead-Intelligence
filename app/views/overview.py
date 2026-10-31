"""Overview: how big is my opportunity, and who do I call first?"""

import plotly.graph_objects as go
import streamlit as st
from common import (
    COMPETITORS,
    EXPLORER,
    GOOD,
    MUTED,
    PRIMARY,
    TIER_COLORS,
    TIER_MEANING,
    TIERS,
    VERTICALS,
    WARN,
    hbar,
    kpi_row,
    last_outcomes,
    lead_row,
    load_leads,
    open_lead,
    reset_filters,
    section,
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
      <div class="line"></div>
      <div class="sub">Which merchants to call first, why, and what to say. Built from public
        website signals on {n:,} Indian D2C, edtech and SaaS businesses.</div>
    </div>""",
    unsafe_allow_html=True,
)

# ---- Quick actions ----
a = st.columns(3)
if a[0].button("Tier A call list", type="primary", use_container_width=True,
               icon=":material/call:"):  # fmt: skip
    reset_filters(f_tier=["A"])
    st.switch_page(EXPLORER)
if a[1].button("Top lead brief", use_container_width=True, icon=":material/target:"):
    open_lead(df.iloc[0]["domain"])
if a[2].button("Competitors", use_container_width=True, icon=":material/explore:"):
    st.switch_page(COMPETITORS)

# ---- Pipeline ----
section("Pipeline", f"{n:,} leads scored · {len(crawled):,} websites analysed")
kpi_row(
    [("Leads scored", f"{n:,}", "D2C · Edtech · SaaS", MUTED)]
    + [
        (
            f"Tier {t}",
            f"{int(counts.get(t, 0)):,}",
            f"{counts.get(t, 0) / n:.0%} of leads · {TIER_MEANING[t].lower()}",
            TIER_COLORS[t],
        )
        for t in TIERS
    ]  # fmt: skip
)

left, right = st.columns(2, gap="medium")
with left, st.container(border=True, height=380):
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
    fig.update_yaxes(autorange="reversed", showgrid=False)
    st.plotly_chart(style_fig(fig, height=330), use_container_width=True, theme=None)

with right, st.container(border=True, height=380):
    fig = go.Figure(
        go.Histogram(
            x=df["score"], xbins=dict(start=0, end=105, size=5), marker_color=PRIMARY,
            marker_line=dict(color="#ffffff", width=2),
            hovertemplate="Score %{x}: <b>%{y}</b> leads<extra></extra>",
        )
    )  # fmt: skip
    for thr, label in [(25, "Tier B ≥ 25"), (40, "Tier A ≥ 40")]:
        fig.add_vline(x=thr, line=dict(color="#334155", width=1, dash="dot"),
                      annotation_text=label, annotation_position="top right",
                      annotation_font_color="#334155")  # fmt: skip
    fig.update_layout(title="Score distribution")
    fig.update_xaxes(title="ICP score (0–100)", showgrid=False)
    fig.update_yaxes(title="Leads")
    st.plotly_chart(style_fig(fig, height=330, legend=False), use_container_width=True, theme=None)


# ---- Payment stack ----
def share(mask) -> str:
    return f"{mask.mean():.0%}" if len(mask) else "—"


section("Payment stack", "What is visible on public pages of crawled sites")
strong_gw = crawled["gateway_confidence"].isin(["high", "medium"])
kpi_row([
    ("Gateway visible", share(strong_gw), "high/medium confidence · a floor", PRIMARY,
     "Gateways usually load only at the final payment step, so this is a minimum."),
    ("Checkout layer", share(crawled["checkout_layer"].notna()), "GoKwik, Magic, Shopflo…",
     "#14b8a6"),
    ("Subscriptions", share(crawled["has_subscription"].fillna(False).astype(bool)),
     "recurring plans or renewals", WARN),
    ("International", share(crawled["has_international"].fillna(False).astype(bool)),
     "overseas shipping or USD pricing", GOOD),
])  # fmt: skip

left, right = st.columns(2, gap="medium")
with left, st.container(border=True, height=380):
    gw = crawled["gateway_names"].explode().dropna().value_counts().head(8)
    if gw.empty:
        st.info("No gateway visible yet.")
    else:
        st.plotly_chart(hbar(gw, "Gateways seen (top 8)", len(crawled)),
                        use_container_width=True, theme=None)  # fmt: skip
with right, st.container(border=True, height=380):
    layers = crawled["checkout_layer_name"].dropna().value_counts()
    if layers.empty:
        st.info("No checkout layer visible yet.")
    else:
        st.plotly_chart(hbar(layers, "Checkout layers seen", len(crawled), color="#14b8a6"),
                        use_container_width=True, theme=None)  # fmt: skip

# ---- Call first ----
section("Call these first", "Top Tier A leads by score")
vert = st.segmented_control("Vertical", ["All", *VERTICALS], default="All", key="ov_vertical",
                            label_visibility="collapsed")  # fmt: skip
top = df[df["tier"] == "A"]
if vert and vert != "All":
    top = top[top["vertical_label"] == vert]
top = top.head(10)
if top.empty:
    st.info("No Tier A leads in this vertical yet. Try Tier B in the Lead Explorer.")
else:
    logged = last_outcomes()
    for i, (_, lead) in enumerate(top.iterrows(), start=1):
        lead_row(lead, i, key=f"ov_{vert}", last_call=logged.get(lead["domain"], ""))
