"""Competitor Landscape: who am I competing against, and where?"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import (
    SEQUENTIAL,
    SINGLE,
    VERTICAL_COLORS,
    VERTICALS,
    kpi,
    load_leads,
    page_header,
    style_fig,
)

df = load_leads()
all_crawled = df[df["data_coverage"] == "website"].copy()

page_header(
    "Competitor Landscape",
    f"What's visible in the payment stack of {len(all_crawled)} crawled merchants. Gateways usually "
    "load only at the final payment step, so gateway counts are a floor — checkout layers are far "
    "more visible.",
)

vert = st.segmented_control("Show", ["All verticals", *VERTICALS], default="All verticals",
                            key="cl_vertical")  # fmt: skip
crawled = all_crawled
if vert and vert != "All verticals":
    crawled = all_crawled[all_crawled["vertical_label"] == vert]
n = len(crawled)

# ---- Headline numbers ----
has_gw = crawled["gateway_names"].apply(len) > 0
has_layer = crawled["checkout_layer"].notna()
multi = crawled["gateway_names"].apply(len) > 1
nothing = ~has_gw & ~has_layer


def pct(mask) -> str:
    return f"{mask.mean():.0%} of sites" if n else "—"


c = st.columns(4)
kpi(c[0], "Gateway visible", int(has_gw.sum()), pct(has_gw))
kpi(c[1], "Checkout layer visible", int(has_layer.sum()), pct(has_layer))
kpi(c[2], "Single gateway", int((has_gw & ~multi).sum()), "backup-route pitch", accent="#eb6834")
kpi(c[3], "Nothing visible", int(nothing.sum()),
    (f"{nothing.mean():.0%} — discover on the call" if n else "—"), accent="#8a8984")  # fmt: skip
st.write("")


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
    fig.update_xaxes(showgrid=False, showticklabels=False,
                     range=[0, (counts.max() if len(counts) else 1) * 1.3])  # fmt: skip
    return style_fig(fig, height=max(150, 80 + 40 * len(counts)), legend=False)


share_tab, heat_tab, plat_tab = st.tabs(
    ["Gateways and checkout layers", "Competitor × vertical", "E-commerce platforms"]
)

with share_tab:
    left, right = st.columns(2)
    with left, st.container(border=True):
        gw_counts = crawled["gateway_names"].explode().dropna().value_counts()
        if gw_counts.empty:
            st.info("No gateway visible on these sites.")
        else:
            st.plotly_chart(hbar(gw_counts, "Gateways detected", n), use_container_width=True,
                            theme=None)  # fmt: skip
        conf = crawled["gateway_confidence"].value_counts()
        st.caption(
            f"Evidence: **{conf.get('high', 0)}** high (gateway script on page) · "
            f"**{conf.get('medium', 0)}** medium (checkout layer that runs on it) · "
            f"**{conf.get('low', 0)}** low (named next to payment words)."
        )
    with right, st.container(border=True):
        layer_counts = crawled["checkout_layer_name"].dropna().value_counts()
        if layer_counts.empty:
            st.info("No checkout layer visible on these sites.")
        else:
            st.plotly_chart(hbar(layer_counts, "Checkout layers detected", n),
                            use_container_width=True, theme=None)  # fmt: skip
        st.caption("Mostly D2C brands on Shopify. A paid checkout layer signals a brand that "
                   "invests in conversion.")  # fmt: skip

# ---- Heatmap: payment stack component x vertical (always all verticals) ----
with heat_tab:
    gw_all = all_crawled["gateway_names"].explode().dropna().value_counts()
    layer_all = all_crawled["checkout_layer_name"].dropna().value_counts()
    components = list(gw_all.index) + list(layer_all.index)
    rows = []
    for comp in components:
        row = []
        for v in VERTICALS:
            sub = all_crawled[all_crawled["vertical_label"] == v]
            hit = sub["gateway_names"].apply(lambda g, c=comp: c in g) | (
                sub["checkout_layer_name"] == comp
            )
            row.append(hit.mean() * 100 if len(sub) else 0)
        rows.append(row)
    heat = pd.DataFrame(rows, index=components, columns=VERTICALS)

    with st.container(border=True):
        fig = go.Figure(
            go.Heatmap(
                z=heat.values, x=VERTICALS, y=heat.index,
                colorscale=[[i / 5, c] for i, c in enumerate(SEQUENTIAL)],
                zmin=0, text=[[f"{v:.0f}%" for v in r] for r in heat.values], texttemplate="%{text}",
                xgap=2, ygap=2, colorbar=dict(title="% of vertical", ticksuffix="%"),
                hovertemplate="%{y} in %{x}: <b>%{z:.1f}%</b> of crawled sites<extra></extra>",
            )
        )  # fmt: skip
        fig.update_layout(title="Where each competitor shows up (% of crawled sites per vertical)")
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(showgrid=False)
        st.plotly_chart(style_fig(fig, height=100 + 34 * len(heat), legend=False),
                        use_container_width=True, theme=None)  # fmt: skip
        st.caption("Always shows all verticals. Read across a row to see which vertical a "
                   "competitor owns: GoKwik dominates D2C; edtech and SaaS show almost nothing "
                   "publicly.")  # fmt: skip
    with st.expander("View as table"):
        st.dataframe(heat.round(1), use_container_width=True)

# ---- Platform mix ----
with plat_tab, st.container(border=True):
    plat = all_crawled.groupby(["platform_label", "vertical_label"]).size().unstack(fill_value=0)
    fig = go.Figure()
    for v in VERTICALS:
        if v in plat:
            fig.add_bar(
                x=plat.index, y=plat[v], name=v, marker_color=VERTICAL_COLORS[v],
                marker_cornerradius=4, hovertemplate="%{x} · " + v + ": <b>%{y}</b><extra></extra>",
            )  # fmt: skip
    fig.update_layout(barmode="group", title="E-commerce platform by vertical", bargroupgap=0.08)
    fig.update_yaxes(title="Merchants")
    st.plotly_chart(style_fig(fig, height=380), use_container_width=True, theme=None)
    st.caption("Shopify and WooCommerce merchants can go live through a plugin in a day, which is "
               "why they score extra in the D2C ICP.")  # fmt: skip
