"""Lead Detail: what do I say on this call?"""

import html
import json
import re

import plotly.graph_objects as go
import streamlit as st
from common import TIER_COLORS, TIER_MEANING, chips, load_leads, style_fig, tier_badge

df = load_leads()
domains = df["domain"].tolist()  # already sorted by score, best first

# Which lead: a page that sent us here > ?domain=... in the URL > last viewed > top lead
domain = (st.session_state.pop("nav_domain", None) or st.query_params.get("domain")
          or st.session_state.get("selected_domain") or domains[0])  # fmt: skip
if domain not in domains:
    domain = domains[0]


def go_to(d: str) -> None:
    st.session_state["nav_domain"] = d


# ---- Lead picker + previous / next ----
labels = {d: f"{n} — {d} (Tier {t}, score {s})" for d, n, t, s in
          zip(df["domain"], df["name"], df["tier"], df["score"], strict=True)}  # fmt: skip
i = domains.index(domain)
top = st.columns([6, 1, 1], vertical_alignment="bottom")
domain = top[0].selectbox("Lead (ranked by score)", domains, index=i, format_func=labels.get)
i = domains.index(domain)
top[1].button("← Previous", use_container_width=True, disabled=i == 0,
              on_click=go_to, args=(domains[max(i - 1, 0)],))  # fmt: skip
top[2].button("Next →", use_container_width=True, disabled=i == len(domains) - 1,
              on_click=go_to, args=(domains[min(i + 1, len(domains) - 1)],))  # fmt: skip

st.query_params["domain"] = domain
st.session_state["selected_domain"] = domain
lead = df[df["domain"] == domain].iloc[0]

# ---- Header ----
meta = [lead["vertical_label"], (lead["sub_category"] or "").title() or None,
        lead["city"] if lead["city"] != "—" else None,
        f"Funding: {lead['funding_stage']}" if lead["funding_stage"] else "Funding: unknown"]  # fmt: skip
with st.container(border=True):
    h = st.columns([5, 1.2], vertical_alignment="center")
    h[0].markdown(
        f'<span class="lead-name">{html.escape(lead["name"])}</span>{tier_badge(lead["tier"])}'
        f'<span class="muted">&nbsp; {TIER_MEANING[lead["tier"]]} · rank {i + 1} of {len(domains)}</span>'
        f'<div class="lead-meta"><a href="https://{domain}" target="_blank">{domain}</a> · '
        + " · ".join(html.escape(str(m)) for m in meta if m)
        + "</div>",
        unsafe_allow_html=True,
    )
    h[1].link_button("Visit website ↗", f"https://{domain}", use_container_width=True)

if lead["data_coverage"] == "seed_only":
    st.warning("This site blocks automated checks, so the score uses seed data only. "
               "Research the site manually before calling.", icon="⚠️")  # fmt: skip

brief, signals = st.tabs(["📞 Call brief", "🔍 Signals and evidence"])

# ---- Tab 1: call brief ----
with brief:
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
        st.plotly_chart(style_fig(fig, height=230, legend=False), use_container_width=True,
                        theme=None)  # fmt: skip
    with r:
        st.markdown("#### Why this lead")
        for reason in lead["reasons"]:
            st.markdown(f'<div class="reason">{html.escape(reason)}</div>', unsafe_allow_html=True)
    with p:
        st.markdown("#### What to pitch")
        st.markdown(chips(lead["suggested_products"]), unsafe_allow_html=True)
        st.markdown("#### Contact")
        if lead["contact_email"]:
            st.code(lead["contact_email"], language=None)
        else:
            st.markdown('<span class="muted">No public business email found.</span>',
                        unsafe_allow_html=True)  # fmt: skip

    st.markdown("#### Opening line")
    st.code(lead["opener"], language=None, wrap_lines=True)
    st.caption("Use the copy icon on the right. Numbers and claims come only from public signals.")

    st.markdown("#### BANT — best public guess, verify on the call")
    b = st.columns(4)
    for col, (label, key) in zip(b, [("💰 Budget", "bant_budget"), ("👤 Authority", "bant_authority"),
                                     ("🎯 Need", "bant_need"), ("⏱ Timeline", "bant_timeline")],
                                 strict=True):  # fmt: skip
        with col.container(border=True, height="stretch"):
            st.markdown(f"**{label}**")
            st.markdown(
                f'<span class="muted">{html.escape(lead[key])}</span>', unsafe_allow_html=True
            )

# ---- Tab 2: signals with evidence ----
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
    return "✅ Yes" if v is True else ("— No" if v is False else "—")


with signals:
    gw_ev = "; ".join(ev(f"gateway:{gw}") for gw in lead["gateways_detected"])
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
    st.caption("Every signal the crawler found, and exactly where it was seen. "
               "Confidence: high = the vendor's own script · medium = a checkout layer that runs "
               "on it · low = named next to payment words.")  # fmt: skip
    st.dataframe(
        [{"Signal": s, "Value": v, "Evidence": e} for s, v, e in rows],
        hide_index=True, use_container_width=True,
        column_config={"Evidence": st.column_config.TextColumn(width="large")},
    )  # fmt: skip
