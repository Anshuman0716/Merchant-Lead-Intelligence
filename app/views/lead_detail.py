"""Lead Detail: who is this company, what do I say, and what happened on the call?"""

import html
import json
import re
from datetime import date, timedelta

import streamlit as st
from common import (
    TIER_MEANING,
    append_call_log,
    chips,
    load_icps,
    load_leads,
    read_call_log,
    section,
    tier_badge,
    vertical_chip,
)

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
labels = {d: f"{n} · {d} (Tier {t}, score {s})" for d, n, t, s in
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
icp = load_icps().get(lead["icp"], {})
esc = html.escape

# ---- Company profile ----
funding = lead["funding_stage"] or "Unknown"
facts = [
    ("Company", esc(lead["name"])),
    ("Website", f'<a href="https://{domain}" target="_blank">https://{esc(domain)} ↗</a>'),
    ("Domain", esc(domain)),
    ("City", esc(lead["city"])),
    ("Vertical", vertical_chip(lead["vertical_label"])),
    ("Category", esc((lead["sub_category"] or "—").title())),
    ("Platform", esc(lead["platform_label"])),
    ("Funding", esc(funding)),
]
with st.container(border=True):
    st.markdown(
        f"""<div class="profile">
          <div>
            <span class="lead-name">{esc(lead["name"])}</span>{tier_badge(lead["tier"])}
            <div class="lead-sub"><b>{TIER_MEANING[lead["tier"]]}</b> · rank {i + 1} of
              {len(domains):,} · {esc(icp.get("label", lead["icp"]))}</div>
          </div>
          <div class="scorebox"><div class="s-num">{int(lead["score"])}</div>
            <div class="s-label">ICP score / 100</div></div>
        </div>
        <div class="facts">"""
        + "".join(
            f'<div class="fact"><div class="f-label">{k}</div><div class="f-value">{v}</div></div>'
            for k, v in facts
        )  # fmt: skip
        + "</div>",
        unsafe_allow_html=True,
    )

if lead["data_coverage"] == "seed_only":
    st.warning("This site blocks automated checks, so the score uses seed data only. "
               "Research the site manually before calling.", icon="⚠️")  # fmt: skip

brief, log_tab, signals = st.tabs(["📞 Call brief", "📝 SDR log", "🔍 Signals and evidence"])

# ---- Tab 1: call brief ----
with brief:
    section("Call brief", "Everything you need before dialling")
    left, right = st.columns([1.5, 1], gap="large")
    with left:
        st.markdown("#### Why this lead")
        reasons = list(lead["reasons"])[:3] or ["No strong public signal; qualify on the call."]
        st.markdown('<ol class="why">' + "".join(f"<li>{esc(r)}</li>" for r in reasons) + "</ol>",
                    unsafe_allow_html=True)  # fmt: skip
        st.markdown("#### What to pitch")
        st.markdown(chips(lead["suggested_products"]), unsafe_allow_html=True)
    with right, st.container(border=True):
        st.markdown("#### Contact information")
        email = lead["contact_email"]
        rows = [
            ("Email", f'<a href="mailto:{esc(email)}">{esc(email)}</a>' if email
             else '<span class="muted">No public business email found</span>'),
            ("Website", f'<a href="https://{domain}" target="_blank">{esc(domain)}</a>'),
            ("Who to ask for", esc(icp.get("buyer", "Founder"))),
            ("Location", esc(lead["city"])),
        ]  # fmt: skip
        st.markdown("".join(f'<div class="contact-row"><div class="c-label">{k}</div>'
                            f'<div class="c-value">{v}</div></div>' for k, v in rows),
                    unsafe_allow_html=True)  # fmt: skip
        st.link_button("Visit website", f"https://{domain}", use_container_width=True,
                       icon=":material/open_in_new:")  # fmt: skip

    st.markdown("#### Opening line")
    st.markdown(f'<div class="opener">{esc(lead["opener"])}</div>', unsafe_allow_html=True)
    st.caption("Built only from public signals. Confirm details on the call.")

    section("BANT qualification", "Our best public guess per section. Confirm it on the call "
            "and record what you learn in the SDR log tab.")  # fmt: skip
    BANT = [("💰", "Budget", "bant_budget", "Can they pay?"),
            ("👤", "Authority", "bant_authority", "Who decides?"),
            ("🎯", "Need", "bant_need", "What problem do we solve?"),
            ("⏱", "Timeline", "bant_timeline", "When will they act?")]  # fmt: skip
    last = read_call_log().query("domain == @domain").sort_values("logged_at").tail(1)
    cols = st.columns(4, gap="small")
    for col, (ico, label, key, q) in zip(cols, BANT, strict=True):
        status = last.iloc[0][f"{label.lower()}_status"] if len(last) else "Not verified"
        color = {"Confirmed": "#059669", "Partly": "#d97706", "Not a fit": "#e11d48"}.get(
            status, "#64748b"
        )
        with col.container(border=True, height="stretch"):
            st.markdown(
                f'<div class="bant-head"><span class="bant-ico">{ico}</span>{label}</div>'
                f'<div class="bant-tag">Public guess</div>'
                f'<div class="bant-guess">{esc(lead[key])}</div>'
                f'<div class="bant-tag">Ask: {q}</div>'
                f'<div style="margin-top:8px"><span class="chip" style="background:#fff;'
                f'color:{color};border-color:{color}">{esc(status)}</span></div>',
                unsafe_allow_html=True,
            )

# ---- Tab 2: SDR log ----
STATUSES = ["Not verified", "Confirmed", "Partly", "Not a fit"]
OUTCOMES = ["Connected", "Meeting booked", "Call back later", "Voicemail", "No answer",
            "Not interested", "Wrong contact"]  # fmt: skip
with log_tab:
    section("Log a call", f"Record what you learned from {esc(lead['name'])}")
    with st.form(f"log_{domain}", clear_on_submit=True, border=True):
        h = st.columns([1.2, 1.2, 1])
        sdr = h[0].text_input("Your name", value=st.session_state.get("sdr_name", ""),
                              placeholder="e.g. Priya")  # fmt: skip
        outcome = h[1].selectbox("Call outcome", OUTCOMES)
        follow = h[2].date_input("Follow-up date", value=date.today() + timedelta(days=3))

        st.markdown("**BANT findings**")
        b = st.columns(4, gap="small")
        entry = {}
        for col, (ico, label, _key, q) in zip(b, BANT, strict=True):
            with col:
                entry[f"{label.lower()}_status"] = st.selectbox(f"{ico} {label}", STATUSES,
                                                                key=f"st_{label}")  # fmt: skip
                entry[f"{label.lower()}_notes"] = st.text_area(
                    f"{label} notes",
                    placeholder=q,
                    height=90,
                    key=f"nt_{label}",
                    label_visibility="collapsed",
                )
        n = st.columns([1.2, 2])
        next_step = n[0].selectbox("Next step", ["Send deck", "Book demo", "Send pricing",
                                                 "Intro to decision maker", "Nurture", "Close lost"])  # fmt: skip
        notes = n[1].text_input("Notes", placeholder="Anything else worth remembering")
        if st.form_submit_button("Save call log", type="primary", icon=":material/save:"):
            st.session_state["sdr_name"] = sdr
            append_call_log({**entry, "domain": domain, "company": lead["name"], "sdr": sdr,
                             "outcome": outcome, "next_step": next_step,
                             "follow_up": follow.isoformat(), "notes": notes})  # fmt: skip
            st.toast(f"Saved call log for {lead['name']}", icon="✅")

    section("Call history")
    hist = read_call_log().query("domain == @domain").sort_values("logged_at", ascending=False)
    if hist.empty:
        st.caption("No calls logged for this lead yet.")
    for _, r in hist.iterrows():
        with st.container(border=True):
            st.markdown(
                f'**{esc(r["outcome"])}** · <span class="muted">{esc(r["logged_at"])}'
                f"{' · by ' + esc(r['sdr']) if r['sdr'] else ''} · next: {esc(r['next_step'])}"
                f" (follow up {esc(r['follow_up'])})</span>",
                unsafe_allow_html=True,
            )
            c = st.columns(4, gap="small")
            for col, (_, label, _, _) in zip(c, BANT, strict=True):
                k = label.lower()
                col.markdown(f'<div class="lr-label">{label}: {esc(r[k + "_status"])}</div>'
                             f'<div class="muted">{esc(r[k + "_notes"]) or "—"}</div>',
                             unsafe_allow_html=True)  # fmt: skip
            if r["notes"]:
                st.markdown(
                    f'<div class="muted">📝 {esc(r["notes"])}</div>', unsafe_allow_html=True
                )

# ---- Tab 3: signals with evidence ----
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
    section("Signals and evidence", "Every signal the crawler found, and exactly where")
    st.caption("Confidence: high = the vendor's own script · medium = a checkout layer that runs "
               "on it · low = named next to payment words.")  # fmt: skip
    st.dataframe(
        [{"Signal": s, "Value": v, "Evidence": e} for s, v, e in rows],
        hide_index=True, use_container_width=True,
        column_config={"Evidence": st.column_config.TextColumn(width="large")},
    )  # fmt: skip
