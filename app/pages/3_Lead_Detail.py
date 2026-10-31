"""Lead Detail: what do I say on this call?"""

import json
import re

import plotly.graph_objects as go
import streamlit as st
from common import TIER_COLORS, chips, load_leads, page_setup, style_fig, tier_badge

page_setup("Lead Detail", "🎯")
df = load_leads()

# Which lead: ?domain=... in the URL, then the row picked on another page, then the top lead
domains = df["domain"].tolist()
default = st.query_params.get("domain") or st.session_state.get("selected_domain") or domains[0]
labels = {d: f"{n} — {d} (Tier {t}, {s})" for d, n, t, s in
          zip(df["domain"], df["name"], df["tier"], df["score"], strict=True)}  # fmt: skip
domain = st.selectbox("Lead", domains, index=domains.index(default) if default in domains else 0,
                      format_func=labels.get)  # fmt: skip
st.query_params["domain"] = domain
st.session_state["selected_domain"] = domain
lead = df[df["domain"] == domain].iloc[0]

# ---- Header ----
meta = [lead["vertical_label"], lead["sub_category"], lead["city"] if lead["city"] != "—" else None,
        f"Funding: {lead['funding_stage']}" if lead["funding_stage"] else "Funding: unknown"]  # fmt: skip
st.markdown(
    f"## {lead['name']} &nbsp;{tier_badge(lead['tier'])}\n"
    f'<p class="muted"><a href="https://{domain}" target="_blank">{domain}</a> · '
    + " · ".join(str(m).title() if m == lead["sub_category"] else str(m) for m in meta if m)
    + "</p>",
    unsafe_allow_html=True,
)
if lead["data_coverage"] == "seed_only":
    st.warning("This site blocks automated checks, so the score uses seed data only. "
               "Research the site manually before calling.")  # fmt: skip

# ---- Score, reasons, products ----
g, r, p = st.columns([1, 1.6, 1.1])
with g:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number", value=int(lead["score"]), number=dict(font=dict(size=44)),
            gauge=dict(
                axis=dict(range=[0, 100], tickvals=[0, 25, 40, 100], tickcolor="#8a8984"),
                bar=dict(color=TIER_COLORS[lead["tier"]], thickness=0.35),
                bgcolor="#f3f2ef", borderwidth=0,
                steps=[dict(range=[25, 40], color="#e8f0fb"), dict(range=[40, 100], color="#dbe8f9")],
            ),
        )
    )  # fmt: skip
    fig.update_layout(title=f"ICP score · {lead['icp'].replace('_', ' ')}")
    st.plotly_chart(style_fig(fig, height=230, legend=False), use_container_width=True, theme=None)
with r:
    st.markdown("#### Why this lead")
    for reason in lead["reasons"]:
        st.markdown(f'<div class="reason">{reason}</div>', unsafe_allow_html=True)
with p:
    st.markdown("#### Pitch")
    st.markdown(chips(lead["suggested_products"]), unsafe_allow_html=True)
    if lead["contact_email"]:
        st.markdown(f'<p class="muted">Public contact: <b>{lead["contact_email"]}</b></p>',
                    unsafe_allow_html=True)  # fmt: skip

# ---- Opener ----
st.markdown("#### Opening line")
st.code(lead["opener"], language=None, wrap_lines=True)
st.caption("Use the copy icon on the right. Numbers and claims come only from public signals.")

# ---- BANT ----
st.markdown("#### BANT (best public guess — verify on the call)")
b = st.columns(4)
for col, (label, key) in zip(b, [("Budget", "bant_budget"), ("Authority", "bant_authority"),
                                 ("Need", "bant_need"), ("Timeline", "bant_timeline")], strict=True):  # fmt: skip
    with col.container(border=True):
        st.markdown(f"**{label}**")
        st.markdown(f'<span class="muted">{lead[key]}</span>', unsafe_allow_html=True)

# ---- Signals with evidence ----
st.markdown("#### Signals and evidence")
evidence = json.loads(lead["evidence"]) if lead["evidence"] else {}


WHERE = {"script": "script", "html": "page code", "links": "link to", "img": "logo",
         "text": "mentions", "page": "page found:"}  # fmt: skip


def readable(pattern: str) -> str:
    """Turn a regex rule into something an SDR can read: '\\bauto[- ]?renew' -> 'auto-renew'."""
    s = re.sub(r"\\b|\\s\*|\\s\?|\(\?:", "", pattern)
    s = (
        s.replace("[- ]?", "-")
        .replace("[- ]", "-")
        .replace("\\d+", "N")
        .replace("\\d", "")
        .replace("\\$", "$")
    )
    s = re.sub(r"\)\??|\?|\\", "", s)
    return s.replace("|", " / ").strip()


def ev(key: str) -> str:
    e = evidence.get(key)
    if not e:
        return ""
    lvl = f" · {e['level']} confidence" if e.get("level") else ""
    return f'{WHERE.get(e.get("where"), "")} "{readable(e["match"])}" on {e["page"]} page{lvl}'


def yes(v) -> str:
    return "Yes" if v is True else ("No" if v is False else "—")


gw_ev = "; ".join(ev(f"gateway:{g}") for g in lead["gateways_detected"])
rows = [
    ("Platform", lead["platform_label"], ev(f"platform:{lead['platform']}")),
    ("Gateway(s)", ", ".join(lead["gateway_names"]) or "Not visible", gw_ev),
    ("Checkout layer", lead["checkout_layer_name"] or "None seen",
     ev(f"checkout:{lead['checkout_layer']}") if lead["checkout_layer"] else ""),
    ("Subscriptions", yes(lead["has_subscription"]), ev("feature:subscription")),
    ("International", yes(lead["has_international"]), ev("feature:international")),
    ("EMI / instalments", yes(lead["has_emi"]), ev("feature:emi")),
    ("Cash on delivery", yes(lead["has_cod"]), ev("feature:cod")),
    ("Android app", yes(lead["has_android_app"]), ev("feature:android_app")),
    ("iOS app", yes(lead["has_ios_app"]), ev("feature:ios_app")),
    ("Pricing page", yes(lead["has_pricing_page"]), ev("feature:pricing_page")),
    ("Pages crawled", str(int(lead["pages_crawled"] or 0)), ""),
]  # fmt: skip
st.dataframe(
    [{"Signal": s, "Value": v, "Evidence": e} for s, v, e in rows],
    hide_index=True, use_container_width=True,
    column_config={"Evidence": st.column_config.TextColumn(width="large")},
)  # fmt: skip
