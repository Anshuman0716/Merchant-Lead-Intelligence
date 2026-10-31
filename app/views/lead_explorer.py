"""Lead Explorer: who do I call today?"""

import streamlit as st
from common import (
    FILTER_DEFAULTS,
    GOOD,
    MUTED,
    TIER_COLORS,
    TIERS,
    VERTICALS,
    kpi_row,
    last_outcomes,
    lead_row,
    load_leads,
    page_header,
    reset_filters,
    restore_filters,
    save_filters,
    section,
)

PAGE_SIZE = 15
df = load_leads()
restore_filters()

page_header("Lead Explorer", "Search for a company or narrow the list with filters, then open "
            "the lead's call brief.")  # fmt: skip

SORTS = {
    "Score (high → low)": (["score", "name"], [False, True]),
    "Score (low → high)": (["score", "name"], [True, True]),
    "Company (A → Z)": (["name"], [True]),
}
names = dict(zip(df["domain"], df["name"], strict=True))
by_name = sorted(names, key=lambda d: names[d].lower())

# ---- Search + filters ----
with st.container(border=True):
    st.selectbox(
        "Search for a company", by_name, key="f_search", accept_new_options=True,
        format_func=lambda d: f"{names[d]}  ·  {d}" if d in names else f'Contains "{d}"',
        placeholder="Start typing a company name (suggestions appear A → Z)…",
        help="Pick a suggestion to see one company, or type any text and press Enter to "
             "match every company or domain that contains it.",
    )  # fmt: skip
    r1 = st.columns([1, 1.4])
    r1[0].pills("Tier", TIERS, selection_mode="multi", key="f_tier")
    r1[1].pills("Vertical", VERTICALS, selection_mode="multi", key="f_vertical")

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
    b = st.columns([4, 1], vertical_alignment="center")
    b[0].caption(f"**{active}** filter{'s' if active != 1 else ''} active" if active
                 else "No filters applied. Showing every lead.")  # fmt: skip
    b[1].button("Reset filters", on_click=reset_filters, use_container_width=True,
                disabled=not active, icon=":material/restart_alt:")  # fmt: skip

save_filters()
s = st.session_state

# ---- Apply filters ----
view = df
if s.f_search:
    if s.f_search in names:
        view = view[view["domain"] == s.f_search]
    else:
        q = str(s.f_search).strip().lower()
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
section("Results")
kpi_row([
    ("Leads shown", f"{len(view):,}", f"of {len(df):,} total", MUTED),
    ("Tier A in view", int((view["tier"] == "A").sum()), "call this week", TIER_COLORS["A"]),
    ("Average score", f"{view['score'].mean():.0f}" if len(view) else "—", "out of 100",
     TIER_COLORS["B"]),
    ("With public email", int(view["contact_email"].notna().sum()), "reachable directly", GOOD),
])  # fmt: skip

if view.empty:
    st.info("No leads match these filters. Try removing one, or press **Reset filters**.")
    st.stop()

# ---- Lead list (paged; resets to page 1 whenever the filters change) ----
sig = repr([s[k] for k in FILTER_DEFAULTS])
if s.get("_ex_sig") != sig:
    s["_ex_sig"], s["ex_page"] = sig, 1
pages = max(1, -(-len(view) // PAGE_SIZE))
s["ex_page"] = min(max(1, s.get("ex_page", 1)), pages)
start = (s["ex_page"] - 1) * PAGE_SIZE

section("Lead list", f"Showing {start + 1}–{min(start + PAGE_SIZE, len(view))} of {len(view):,}")
logged = last_outcomes()
for i, (_, lead) in enumerate(view.iloc[start : start + PAGE_SIZE].iterrows(), start=start + 1):
    lead_row(lead, i, key="ex", opener=False, last_call=logged.get(lead["domain"], ""))


def move(step: int) -> None:
    st.session_state["ex_page"] += step


p = st.columns([1, 2, 1], vertical_alignment="center")
p[0].button("← Previous", on_click=move, args=(-1,), disabled=s["ex_page"] == 1,
            use_container_width=True)  # fmt: skip
p[1].markdown(f'<div style="text-align:center" class="muted">Page <b>{s["ex_page"]}</b> of '
              f"<b>{pages}</b></div>", unsafe_allow_html=True)  # fmt: skip
p[2].button("Next →", on_click=move, args=(1,), disabled=s["ex_page"] == pages,
            use_container_width=True)  # fmt: skip

# ---- Export ----
st.write("")
export = view[["name", "domain", "vertical_label", "tier", "score", "city", "payment_stack",
               "contact_email", "opener"]].copy()  # fmt: skip
export["reasons"] = view["reasons"].apply(" | ".join)
export["suggested_products"] = view["suggested_products"].apply("; ".join)
st.download_button(f"Download these {len(view):,} leads (CSV)",
                   export.to_csv(index=False).encode("utf-8"), icon=":material/download:",
                   file_name="filtered_leads.csv", mime="text/csv")  # fmt: skip
