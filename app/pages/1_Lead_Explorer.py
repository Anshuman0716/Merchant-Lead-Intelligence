"""Lead Explorer: who do I call today?"""

import streamlit as st
from common import TIERS, VERTICALS, load_leads, open_lead, page_setup

page_setup("Lead Explorer", "🔎")
df = load_leads()

st.title("Lead Explorer")
st.caption("Filter, sort and export. Select a row to open the lead brief.")

# ---- Filters (one block above the table) ----
r1 = st.columns([2, 1.2, 1.2, 1.4])
search = r1[0].text_input("Search company or domain", placeholder="e.g. mamaearth")
verticals = r1[1].multiselect("Vertical", VERTICALS, placeholder="All")
tiers = r1[2].multiselect("Tier", TIERS, placeholder="All")
platforms = r1[3].multiselect("Platform", sorted(df["platform_label"].dropna().unique()),
                              placeholder="All")  # fmt: skip

r2 = st.columns([1.4, 1.4, 1.4, 1.2])
all_gw = sorted({g for gws in df["gateway_names"] for g in gws})
gateways = r2[0].multiselect("Gateway detected", all_gw, placeholder="Any")
layers = r2[1].multiselect("Checkout layer", sorted(df["checkout_layer_name"].dropna().unique()),
                           placeholder="Any")  # fmt: skip
cities = r2[2].multiselect("City", sorted(c for c in df["city"].unique() if c != "—"),
                           placeholder="All")  # fmt: skip
funded = r2[3].selectbox("Funding", ["Any", "Funding known", "Funding unknown"])

with st.expander("More filters"):
    f = st.columns(4)
    need_sub = f[0].checkbox("Sells subscriptions")
    need_intl = f[1].checkbox("Sells internationally")
    need_email = f[2].checkbox("Has public email")
    hide_seed = f[3].checkbox("Hide sites we couldn't crawl")
    min_score = st.slider("Minimum score", 0, 100, 0, step=5)

view = df
if search:
    s = search.strip().lower()
    view = view[view["name"].str.lower().str.contains(s, regex=False)
                | view["domain"].str.contains(s, regex=False)]  # fmt: skip
if verticals:
    view = view[view["vertical_label"].isin(verticals)]
if tiers:
    view = view[view["tier"].isin(tiers)]
if platforms:
    view = view[view["platform_label"].isin(platforms)]
if gateways:
    view = view[view["gateway_names"].apply(lambda g: bool(set(g) & set(gateways)))]
if layers:
    view = view[view["checkout_layer_name"].isin(layers)]
if cities:
    view = view[view["city"].isin(cities)]
if funded != "Any":
    view = view[view["is_funded"] == (funded == "Funding known")]
if need_sub:
    view = view[view["has_subscription"].fillna(False).astype(bool)]
if need_intl:
    view = view[view["has_international"].fillna(False).astype(bool)]
if need_email:
    view = view[view["contact_email"].notna()]
if hide_seed:
    view = view[view["data_coverage"] == "website"]
view = view[view["score"] >= min_score]

# ---- Table ----
m = st.columns([1, 1, 1, 3])
m[0].metric("Leads shown", len(view))
m[1].metric("Tier A in view", int((view["tier"] == "A").sum()))
m[2].metric("Avg score", f"{view['score'].mean():.0f}" if len(view) else "—")

table = view.assign(website="https://" + view["domain"])[
    ["name", "vertical_label", "tier", "score", "platform_label", "payment_stack", "top_reason",
     "city", "website"]
]  # fmt: skip
event = st.dataframe(
    table, hide_index=True, use_container_width=True, height=560,
    on_select="rerun", selection_mode="single-row",
    column_config={
        "name": st.column_config.TextColumn("Company", width="medium"),
        "vertical_label": "Vertical",
        "tier": st.column_config.TextColumn("Tier", width="small"),
        "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
        "platform_label": "Platform",
        "payment_stack": st.column_config.TextColumn("Payment stack (visible)", width="medium"),
        "top_reason": st.column_config.TextColumn("Top reason", width="large"),
        "city": "City",
        "website": st.column_config.LinkColumn("Website", display_text=r"https://(.*)"),
    },
)  # fmt: skip
if event.selection.rows:
    open_lead(view.iloc[event.selection.rows[0]]["domain"])

export = view[["name", "domain", "vertical_label", "tier", "score", "city", "payment_stack",
               "contact_email", "opener"]].copy()  # fmt: skip
export["reasons"] = view["reasons"].apply(" | ".join)
export["suggested_products"] = view["suggested_products"].apply("; ".join)
st.download_button("Download filtered leads (CSV)", export.to_csv(index=False).encode("utf-8"),
                   file_name="filtered_leads.csv", mime="text/csv", type="primary")  # fmt: skip
