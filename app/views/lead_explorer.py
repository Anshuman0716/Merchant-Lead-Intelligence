"""Lead Explorer: who do I call today?"""

import html

import streamlit as st
from common import (
    FILTER_DEFAULTS,
    TIER_COLORS,
    TIERS,
    VERTICALS,
    chips,
    kpi,
    load_leads,
    open_lead,
    page_header,
    reset_filters,
    restore_filters,
    save_filters,
    tier_badge,
)

df = load_leads()
restore_filters()

page_header("Lead Explorer", "Filter, sort and export your leads. Click a row to preview it, "
            "then open the full call brief.")  # fmt: skip

SORTS = {
    "Score (high → low)": (["score", "name"], [False, True]),
    "Score (low → high)": (["score", "name"], [True, True]),
    "Company (A → Z)": (["name"], [True]),
}

# ---- Filters ----
with st.container(border=True):
    r1 = st.columns([2.2, 1.2, 1.6])
    r1[0].text_input("Search company or domain", placeholder="e.g. mamaearth", key="f_search")
    r1[1].pills("Tier", TIERS, selection_mode="multi", key="f_tier")
    r1[2].pills("Vertical", VERTICALS, selection_mode="multi", key="f_vertical")

    r2 = st.columns(4)
    r2[0].multiselect("Platform", sorted(df["platform_label"].dropna().unique()),
                      placeholder="All", key="f_platform")  # fmt: skip
    r2[1].multiselect("Gateway detected", sorted({g for gws in df["gateway_names"] for g in gws}),
                      placeholder="Any", key="f_gateway")  # fmt: skip
    r2[2].multiselect("Checkout layer", sorted(df["checkout_layer_name"].dropna().unique()),
                      placeholder="Any", key="f_layer")  # fmt: skip
    r2[3].multiselect("City", sorted(c for c in df["city"].unique() if c != "—"),
                      placeholder="All", key="f_city")  # fmt: skip

    with st.expander("More filters and sorting"):
        f = st.columns(4)
        f[0].checkbox("Sells subscriptions", key="f_sub")
        f[1].checkbox("Sells internationally", key="f_intl")
        f[2].checkbox("Has public email", key="f_email")
        f[3].checkbox("Hide sites we couldn't crawl", key="f_hide_seed")
        g = st.columns([2, 1, 1])
        g[0].slider("Minimum score", 0, 100, step=5, key="f_min_score")
        g[1].selectbox("Funding", ["Any", "Funding known", "Funding unknown"], key="f_funding")
        g[2].selectbox("Sort by", list(SORTS), key="f_sort")

    active = sum(st.session_state[k] != v for k, v in FILTER_DEFAULTS.items() if k != "f_sort")
    b = st.columns([4, 1])
    b[0].caption(f"**{active}** filter{'s' if active != 1 else ''} active" if active
                 else "No filters applied — showing every lead.")  # fmt: skip
    b[1].button("Reset filters", on_click=reset_filters, use_container_width=True,
                disabled=not active)  # fmt: skip

save_filters()
s = st.session_state

# ---- Apply filters ----
view = df
if s.f_search:
    q = s.f_search.strip().lower()
    view = view[view["name"].str.lower().str.contains(q, regex=False)
                | view["domain"].str.contains(q, regex=False)]  # fmt: skip
if s.f_tier:
    view = view[view["tier"].isin(s.f_tier)]
if s.f_vertical:
    view = view[view["vertical_label"].isin(s.f_vertical)]
if s.f_platform:
    view = view[view["platform_label"].isin(s.f_platform)]
if s.f_gateway:
    view = view[view["gateway_names"].apply(lambda g: bool(set(g) & set(s.f_gateway)))]
if s.f_layer:
    view = view[view["checkout_layer_name"].isin(s.f_layer)]
if s.f_city:
    view = view[view["city"].isin(s.f_city)]
if s.f_funding != "Any":
    view = view[view["is_funded"] == (s.f_funding == "Funding known")]
if s.f_sub:
    view = view[view["has_subscription"].fillna(False).astype(bool)]
if s.f_intl:
    view = view[view["has_international"].fillna(False).astype(bool)]
if s.f_email:
    view = view[view["contact_email"].notna()]
if s.f_hide_seed:
    view = view[view["data_coverage"] == "website"]
view = view[view["score"] >= s.f_min_score]
by, asc = SORTS[s.f_sort]
view = view.sort_values(by, ascending=asc)

# ---- Summary ----
m = st.columns(4)
kpi(m[0], "Leads shown", len(view), f"of {len(df)} total", accent="#52514e")
kpi(m[1], "Tier A in view", int((view["tier"] == "A").sum()), "call this week",
    accent=TIER_COLORS["A"])  # fmt: skip
kpi(m[2], "Average score", f"{view['score'].mean():.0f}" if len(view) else "—", "out of 100")
kpi(m[3], "With public email", int(view["contact_email"].notna().sum()), "reachable directly",
    accent="#1baf7a")  # fmt: skip
st.write("")

if view.empty:
    st.info("No leads match these filters. Try removing one, or press **Reset filters**.")
    st.stop()

# ---- Table ----
table = view.assign(website="https://" + view["domain"])[
    ["name", "tier", "score", "vertical_label", "platform_label", "payment_stack", "top_reason",
     "city", "website"]
]  # fmt: skip
event = st.dataframe(
    table, hide_index=True, use_container_width=True, height=480,
    on_select="rerun", selection_mode="single-row", key="explorer_table",
    column_config={
        "name": st.column_config.TextColumn("Company", width="medium", pinned=True),
        "tier": st.column_config.TextColumn("Tier", width="small"),
        "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
        "vertical_label": "Vertical",
        "platform_label": "Platform",
        "payment_stack": st.column_config.TextColumn("Payment stack (visible)", width="medium"),
        "top_reason": st.column_config.TextColumn("Top reason", width="large"),
        "city": "City",
        "website": st.column_config.LinkColumn("Website", display_text=r"https://(.*)"),
    },
)  # fmt: skip

# ---- Preview of the selected lead ----
rows = event.selection.rows
if rows and rows[0] < len(view):
    lead = view.iloc[rows[0]]
    with st.container(border=True):
        h = st.columns([4, 1])
        h[0].markdown(
            f'<span class="lead-name" style="font-size:1.35rem">{html.escape(lead["name"])}</span>'
            f'{tier_badge(lead["tier"])} <span class="muted">&nbsp;Score <b>{lead["score"]}</b> · '
            f"{lead['vertical_label']} · {lead['payment_stack']}</span>",
            unsafe_allow_html=True,
        )
        if h[1].button("Open full brief →", type="primary", use_container_width=True):
            open_lead(lead["domain"])
        p = st.columns([1.4, 1])
        with p[0]:
            for reason in lead["reasons"]:
                st.markdown(f'<div class="reason">{html.escape(reason)}</div>',
                            unsafe_allow_html=True)  # fmt: skip
        with p[1]:
            st.markdown("**Opener**")
            st.code(lead["opener"], language=None, wrap_lines=True)
            st.markdown(chips(lead["suggested_products"]), unsafe_allow_html=True)
else:
    st.caption("👆 Click any row to preview the lead here.")

# ---- Export ----
export = view[["name", "domain", "vertical_label", "tier", "score", "city", "payment_stack",
               "contact_email", "opener"]].copy()  # fmt: skip
export["reasons"] = view["reasons"].apply(" | ".join)
export["suggested_products"] = view["suggested_products"].apply("; ".join)
st.download_button(f"⬇  Download these {len(view)} leads (CSV)",
                   export.to_csv(index=False).encode("utf-8"),
                   file_name="filtered_leads.csv", mime="text/csv")  # fmt: skip
