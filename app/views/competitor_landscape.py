"""Competitor Landscape: who am I competing against, where, and how do I win?"""

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import (
    MUTED,
    PRIMARY,
    SEQUENTIAL,
    VERTICAL_COLORS,
    VERTICALS,
    WARN,
    hbar,
    kpi_row,
    lead_row,
    load_competitors,
    load_leads,
    page_header,
    section,
    style_fig,
)

df = load_leads()
comp = load_competitors()
all_crawled = df[df["data_coverage"] == "website"].copy()
esc = html.escape

page_header(
    "Competitor Landscape",
    f"Who processes payments for the {len(all_crawled):,} merchants we crawled, and how to win "
    f"against each one. Battlecards researched from public sources ({comp['as_of']}).",
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


kpi_row([
    ("Gateway visible", int(has_gw.sum()), pct(has_gw), PRIMARY),
    ("Checkout layer visible", int(has_layer.sum()), pct(has_layer), "#14b8a6"),
    ("Single gateway", int((has_gw & ~multi).sum()), "backup-route pitch", WARN),
    ("Nothing visible", int(nothing.sum()),
     f"{nothing.mean():.0%} · discover on the call" if n else "—", MUTED),
])  # fmt: skip

cards_tab, share_tab, heat_tab, plat_tab = st.tabs(
    [
        "⚔️ Battlecards",
        "Gateways and checkout layers",
        "Competitor × vertical",
        "E-commerce platforms",
    ]  # fmt: skip
)

# ---- Battlecards ----
THREAT = {"High": ("#fff1f2", "#be123c"), "Medium": ("#fffbeb", "#b45309"),
          "Low": ("#ecfdf5", "#047857")}  # fmt: skip


def bullets(items) -> str:
    return '<ul class="bc-list">' + "".join(f"<li>{esc(str(x))}</li>" for x in items) + "</ul>"


with cards_tab:
    gw_counts = crawled["gateway_names"].explode().dropna().value_counts()
    names = list(comp["gateways"])
    names.sort(key=lambda g: -int(gw_counts.get(g, 0)))
    pick = st.pills("Competitor", names, default=names[0], key="cl_comp")
    if pick:
        c = comp["gateways"][pick]
        seen = int(gw_counts.get(pick, 0))
        bg, fg = THREAT.get(c["threat"].split()[0], THREAT["Medium"])
        with st.container(border=True):
            st.markdown(
                f'<div class="bc-head"><span class="bc-name">{esc(pick)}</span>'
                f'<span class="chip">{esc(c["type"])}</span>'
                f'<span class="threat" style="background:{bg};color:{fg}">Threat: '
                f"{esc(c['threat'])}</span></div>"
                f'<div class="lead-sub" style="margin-top:10px">{esc(c["position"])}</div>',
                unsafe_allow_html=True,
            )
            kpi_row([
                ("Seen on merchants", seen, f"{seen / n:.0%} of crawled sites" if n else "—",
                 PRIMARY),
                ("Tier A/B using it", int(crawled[crawled["gateway_names"].apply(
                    lambda g, p=pick: p in g)]["tier"].isin(["A", "B"]).sum()),
                 "ready to pitch", "#3730a3"),
                ("Threat level", esc(c["threat"]), "to Cashfree in this segment", fg),
            ])  # fmt: skip
            st.markdown(
                f'<div class="opener" style="font-size:.92rem;margin-bottom:14px">'
                f"<b>Pricing:</b> {esc(c['pricing'])}</div>",
                unsafe_allow_html=True,
            )
            cols = st.columns(3, gap="medium")
            for col, title, key in zip(cols, ["✅ Their strengths", "⚠️ Their weaknesses",
                                              "🏆 How we win"],
                                       ["strengths", "weaknesses", "win_with"], strict=True):  # fmt: skip
                col.markdown(f'<div class="bc-title">{title}</div>{bullets(c[key])}',
                             unsafe_allow_html=True)  # fmt: skip

        users = crawled[crawled["gateway_names"].apply(lambda g, p=pick: p in g)]
        users = users[users["tier"].isin(["A", "B"])].head(5)
        if len(users):
            section(f"Best leads on {esc(pick)}", "Tier A/B merchants where we saw it")
            for k, (_, lead) in enumerate(users.iterrows(), start=1):
                lead_row(lead, k, key=f"cl_{pick}", opener=False)

    section("Checkout layers", "One-click checkouts that sit in front of the gateway")
    lc = crawled["checkout_layer_name"].dropna().value_counts()
    layers = list(comp["checkout_layers"].items())
    for row in range(0, len(layers), 3):
        cols = st.columns(3, gap="medium")
        for col, (name, info) in zip(cols, layers[row : row + 3], strict=False):
            with col.container(border=True, height="stretch"):
                st.markdown(
                    f'<div class="bc-title">{esc(name)} <span class="muted">· seen on '
                    f'{int(lc.get(name, 0))}</span></div><div class="muted">{esc(info["position"])}'
                    f'</div><div style="margin-top:8px;font-size:.88rem"><b>Pitch:</b> '
                    f"{esc(info['pitch'])}</div>",
                    unsafe_allow_html=True,
                )

    section("Market notes")
    st.markdown(bullets(comp["market_notes"]), unsafe_allow_html=True)
    st.caption("Full research with sources: docs/competitor_analysis.md")

# ---- Share charts ----
with share_tab:
    left, right = st.columns(2, gap="medium")
    with left, st.container(border=True):
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
            st.plotly_chart(hbar(layer_counts, "Checkout layers detected", n, color="#14b8a6"),
                            use_container_width=True, theme=None)  # fmt: skip
        st.caption("Mostly D2C brands on Shopify. A paid checkout layer signals a brand that "
                   "invests in conversion.")  # fmt: skip

# ---- Heatmap: payment stack component x vertical (always all verticals) ----
with heat_tab:
    gw_all = all_crawled["gateway_names"].explode().dropna().value_counts()
    layer_all = all_crawled["checkout_layer_name"].dropna().value_counts()
    components = list(gw_all.index) + list(layer_all.index)
    rows = []
    for comp_name in components:
        row = []
        for v in VERTICALS:
            sub = all_crawled[all_crawled["vertical_label"] == v]
            hit = sub["gateway_names"].apply(lambda g, c=comp_name: c in g) | (
                sub["checkout_layer_name"] == comp_name
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
                xgap=3, ygap=3, colorbar=dict(title="% of vertical", ticksuffix="%"),
                hovertemplate="%{y} in %{x}: <b>%{z:.1f}%</b> of crawled sites<extra></extra>",
            )
        )  # fmt: skip
        fig.update_layout(title="Where each competitor shows up (% of crawled sites per vertical)")
        fig.update_yaxes(autorange="reversed", showgrid=False)
        fig.update_xaxes(showgrid=False)
        st.plotly_chart(style_fig(fig, height=110 + 34 * len(heat), legend=False),
                        use_container_width=True, theme=None)  # fmt: skip
        st.caption("Always shows all verticals. Read across a row to see which vertical a "
                   "competitor owns.")  # fmt: skip
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
