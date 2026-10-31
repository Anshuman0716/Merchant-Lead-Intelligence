"""Competitor Landscape: who am I competing against, and where?"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import SEQUENTIAL, SINGLE, VERTICAL_COLORS, VERTICALS, load_leads, page_setup, style_fig

page_setup("Competitor Landscape", "🧭")
df = load_leads()
crawled = df[df["data_coverage"] == "website"].copy()
n = len(crawled)

st.title("Competitor Landscape")
st.caption(
    f"What's visible in the payment stack of {n} crawled merchants. Gateways usually load only at "
    "the final payment step, so gateway counts are a floor — checkout layers are far more visible."
)

# ---- Headline numbers ----
has_gw = crawled["gateway_names"].apply(len) > 0
has_layer = crawled["checkout_layer"].notna()
multi = crawled["gateway_names"].apply(len) > 1
c = st.columns(4)
c[0].metric("Gateway visible", int(has_gw.sum()), f"{has_gw.mean():.0%} of sites", delta_color="off", delta_arrow="off",
            border=True)  # fmt: skip
c[1].metric("Checkout layer visible", int(has_layer.sum()), f"{has_layer.mean():.0%} of sites",
            delta_color="off", delta_arrow="off", border=True)  # fmt: skip
c[2].metric("Single gateway", int((has_gw & ~multi).sum()), "of sites with a gateway visible",
            delta_color="off", delta_arrow="off", border=True)  # fmt: skip
c[3].metric("Nothing visible", int((~has_gw & ~has_layer).sum()),
            f"{(~has_gw & ~has_layer).mean():.0%} — discover on the call", delta_color="off", delta_arrow="off",
            border=True)  # fmt: skip


def hbar(counts: pd.Series, title: str, total: int) -> go.Figure:
    counts = counts.sort_values()
    fig = go.Figure(
        go.Bar(
            x=counts.values, y=counts.index, orientation="h", marker_color=SINGLE,
            marker_cornerradius=4, text=[f"{v} ({v / total:.0%})" for v in counts.values],
            textposition="outside", textfont_color="#52514e", cliponaxis=False,
            hovertemplate="%{y}: <b>%{x}</b> merchants<extra></extra>",
        )
    )  # fmt: skip
    fig.update_layout(title=title)
    fig.update_xaxes(showgrid=False, showticklabels=False, range=[0, counts.max() * 1.3])
    return style_fig(fig, height=300, legend=False)


left, right = st.columns(2)
with left:
    gw_counts = crawled["gateway_names"].explode().dropna().value_counts()
    st.plotly_chart(hbar(gw_counts, "Gateways detected (high + medium + low)", n),
                    use_container_width=True, theme=None)  # fmt: skip
    conf = crawled["gateway_confidence"].value_counts()
    st.caption(
        f"Evidence: {conf.get('high', 0)} high (gateway script on page) · {conf.get('medium', 0)} "
        f"medium (checkout layer that runs on it) · {conf.get('low', 0)} low (named next to payment words)."
    )
with right:
    layer_counts = crawled["checkout_layer_name"].dropna().value_counts()
    st.plotly_chart(
        hbar(layer_counts, "Checkout layers detected", n), use_container_width=True, theme=None
    )
    st.caption(
        "Mostly D2C brands on Shopify. A paid checkout layer signals a brand that invests in conversion."
    )

# ---- Heatmap: payment stack component x vertical ----
components = list(gw_counts.index) + list(layer_counts.index)
rows = []
for comp in components:
    row = []
    for v in VERTICALS:
        sub = crawled[crawled["vertical_label"] == v]
        hit = sub["gateway_names"].apply(lambda g, c=comp: c in g) | (
            sub["checkout_layer_name"] == comp
        )
        row.append(hit.mean() * 100 if len(sub) else 0)
    rows.append(row)
heat = pd.DataFrame(rows, index=components, columns=VERTICALS)

fig = go.Figure(
    go.Heatmap(
        z=heat.values, x=VERTICALS, y=heat.index, colorscale=[[i / 5, c] for i, c in enumerate(SEQUENTIAL)],
        zmin=0, text=[[f"{v:.0f}%" for v in r] for r in heat.values], texttemplate="%{text}",
        xgap=2, ygap=2, colorbar=dict(title="% of vertical", ticksuffix="%"),
        hovertemplate="%{y} in %{x}: <b>%{z:.1f}%</b> of crawled sites<extra></extra>",
    )
)  # fmt: skip
fig.update_layout(title="Where each competitor shows up (% of crawled sites per vertical)")
fig.update_yaxes(autorange="reversed", showgrid=False)
fig.update_xaxes(showgrid=False)
st.plotly_chart(
    style_fig(fig, height=80 + 34 * len(heat), legend=False), use_container_width=True, theme=None
)

# ---- Platform mix ----
plat = crawled.groupby(["platform_label", "vertical_label"]).size().unstack(fill_value=0)
fig = go.Figure()
for v in VERTICALS:
    if v in plat:
        fig.add_bar(
            x=plat.index, y=plat[v], name=v, marker_color=VERTICAL_COLORS[v], marker_cornerradius=4,
            hovertemplate="%{x} · " + v + ": <b>%{y}</b><extra></extra>",
        )  # fmt: skip
fig.update_layout(barmode="group", title="E-commerce platform by vertical", bargroupgap=0.08)
fig.update_yaxes(title="Merchants")
st.plotly_chart(style_fig(fig), use_container_width=True, theme=None)

with st.expander("View as table"):
    st.dataframe(heat.round(1), use_container_width=True)
