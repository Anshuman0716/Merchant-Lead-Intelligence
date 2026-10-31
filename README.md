# Merchant Lead Intelligence Engine

> It tells a payments SDR which merchants to call first, why, and what to say.

Takes 300–500 Indian online businesses (D2C, edtech, SaaS), detects their payment setup from
public website signals, scores them against 3 ICPs, and outputs a tiered, CRM-ready lead list
with personalised openers — plus a dashboard and a one-page insight note.

🚧 Work in progress — Phases 0–4 done (universe, crawler, detection, scoring, dashboard, sales docs).

## How to run

```bash
make setup      # install deps
make pipeline   # rebuild everything from data/seeds/
make app        # open the dashboard
make test
```

Stages can be run alone: `uv run python -m leadintel.run --only crawl`, `--from detect`,
`--refresh` (re-fetch cached pages), `--limit 10`.

## Dashboard

`make app` (or `uv run streamlit run app/Home.py`) opens four pages, each answering an SDR question:

| Page | Question it answers |
|---|---|
| Overview | How big is my opportunity? Tier counts, payment-stack KPIs, score distribution, call-first list |
| Lead Explorer | Who do I call today? Filters (vertical, tier, platform, gateway, checkout layer, city, funding), CSV download |
| Competitor Landscape | Who am I up against, and where? Gateway and checkout-layer share, competitor × vertical heatmap |
| Lead Detail | What do I say? Score gauge, top 3 reasons, copyable opener, BANT, every signal with its evidence |

The app reads `exports/leads.parquet` (committed), not the DuckDB file, so it deploys light.
Lead pages are shareable: `/Lead_Detail?domain=livpure.com`.

## Sales artefacts

- [`docs/icp_personas.md`](docs/icp_personas.md): 3 ICP one-pagers
- [`docs/cold_emails.md`](docs/cold_emails.md): 20 cold emails for Tier A leads (under 120 words each)
- [`docs/insight_note.pdf`](docs/insight_note.pdf): one-page findings, built from the data by
  `uv run --with reportlab python scripts/build_insight_note.py`

## HubSpot import

`exports/hubspot_companies.csv` maps to HubSpot companies. First create these custom company
properties (Settings → Properties → Company): **Vertical**, **Lead tier**, **ICP score** (number),
**Current gateway**, **Checkout layer**, **Suggested products**, **Top reasons**, **Opener**
(multi-line text). Then go to Import → Companies → map columns. Name, domain, Industry, City and
Country/Region map to built-in fields. The deal pipeline for 20 Tier A leads is simulated.

## Pipeline

| Stage | Module | Output table |
|---|---|---|
| 1. Ingest seed CSVs | `ingest.py` | `raw_companies` |
| 2. Clean, dedupe, reachability check | `clean.py` | `companies` |
| 3. Polite crawl (≤5 public pages/site) | `crawl.py` | `pages` |
| 4. Fingerprint detection | `detect.py` | `signals` |
| 5. ICP scoring, tiers, openers | `score.py` | `lead_scores` |
| 6. Exports + dashboard | `export.py`, `app/` | `exports/` |

## Current numbers

- **Universe:** 408 seed companies → 364 valid (202 D2C, 81 edtech, 81 SaaS). 44 quarantined,
  not deleted: 25 block bots (403/429 — respected, not bypassed), 16 dead/broken sites,
  2 redirect to another company already in the list (Doubtnut → ALLEN, FabAlley → Indya), 1 other.
- **Crawl:** 1,221 pages cached from 362 sites; 29 page fetches skipped because robots.txt disallows them.
- **Platform:** Shopify 154, WooCommerce 5, custom 204.
- **Checkout layer** found on 38% of sites (GoKwik 90, Razorpay Magic Checkout 20,
  Shiprocket 15, Shopflo 13).
- **Payment gateway** identified on 9% of sites (32): 9 high, 19 medium, 4 low confidence.
- **Leads:** 389 scored (364 crawled + 25 bot-blocked sites scored on seed data only).
  Tier A 55 (14%), B 123 (32%), C 211 (54%). By vertical — A: D2C 31, SaaS 23, edtech 1.

## Ethics

Only public pages. robots.txt respected. Max 1 request / 2 s per site. Honest user agent that
links to this repo. No logins, no form submissions, no test orders, no checkout attempts.
Sites that block bots are marked `blocked`, not bypassed. Contact emails are only kept when
they are role-based (sales@, hello@, support@…) and on the company's own domain.

## Detection: evidence levels

The actual payment gateway usually loads only at the final payment step, which can't be reached
without buying. So every gateway detection records *how* it was found:

| Confidence | Evidence |
|---|---|
| high | The gateway's own script/SDK is on a public page (e.g. `checkout.razorpay.com`) |
| medium | A checkout layer known to run on that gateway (Razorpay Magic Checkout → Razorpay) |
| low | Gateway named in visible text or a payment logo, **next to payment words** |

## Fingerprint verification — what the real pages taught me

Rules live in [`config/fingerprints.yaml`](config/fingerprints.yaml). I checked every rule
against the cached pages and fixed these:

1. `"paypal"` appears on **every** Shopify page (a built-in tracking flag) → only the PayPal SDK URL counts.
2. Paytm / PhonePe appear as UPI-app icons and promo names ("PhonePe flat 20% off") → script-only rules.
3. Edtech sites show Razorpay/CCAvenue as **hiring-partner logos**; SaaS sites quote Razorpay in
   testimonials; founder bios mention "CEO of Cashfree Payments". Low-confidence matches now
   need payment words nearby (e.g. "payment partners: Razorpay PayU").
4. A vendor's own site doesn't count as using its product (chargebee.com ≠ "uses Chargebee").
5. Scanning all script hosts found patterns I hadn't listed: Razorpay payment links (`rzp.io`),
   Recurpay subscriptions, Snapmint pay-later on 31 D2C sites.

Detection accuracy against a 40-site hand-labelled sample: _pending_ (see
[`docs/accuracy/`](docs/accuracy/)).

## How scoring works

Each company is scored on the ICP that matches its vertical (personas: [`docs/icp_personas.md`](docs/icp_personas.md)).
Score = sum of the weights of signals that are true, clipped to 0–100. Tier A ≥ 40, B ≥ 25, else C.
Weights live in [`config/icp.yaml`](config/icp.yaml) — a sales manager can change them without code.

| Signal | D2C growth | Edtech subscription | SaaS global |
|---|---|---|---|
| Competitor gateway (high/medium confidence) | +20 | +15 | +10 |
| Only one gateway detected | +10 | +10 | +5 |
| Already on Cashfree (always Tier C → account manager) | −30 | −30 | −30 |
| Paid checkout layer (GoKwik, Shopflo, Shiprocket) | +10 | 0 | 0 |
| Subscriptions / recurring | +10 | +25 | +20 |
| International sales | +10 | +5 | +30 |
| Funded in last 18 months | +20 | +15 | +15 |
| Shopify / WooCommerce | +10 | 0 | 0 |
| EMI / instalments | +5 | +15 | 0 |
| Mobile app | +5 | +10 | 0 |
| Cash on delivery | +5 | 0 | 0 |
| Public pricing page | 0 | +5 | +5 |
| Public business email | +5 | +5 | +5 |

Every lead stores its **top 3 reasons** in plain English, BANT best guesses (marked "to verify on
call"), up to 3 suggested products and a one-line opener chosen from its strongest reason.

### Tuning log

1. **Razorpay Magic Checkout was counted three times** (competitor gateway + single gateway +
   checkout layer = 40 points from one script, and three reasons saying the same thing). Now a
   checkout layer that reveals the gateway only scores as a gateway signal.
2. **Added two signals the plan didn't have.** *Paid checkout layer* (+10 D2C): gateways are
   visible on only 9% of sites but checkout layers on 38%, and paying for GoKwik shows a brand
   cares about conversion. *EMI / instalments* (+15 edtech): matches the edtech pain (course-fee EMIs).
3. **Lowered tier thresholds from A ≥ 65 / B ≥ 40 to A ≥ 40 / B ≥ 25.** With funding data still
   empty and gateway signals rare, almost nothing could reach 65 (2% Tier A). Adjusted
   thresholds, not data. Revisit once funding dates are filled in.

Known gaps from the sanity review: edtech sites expose few payment signals on public pages
(1 Tier A edtech lead); company size isn't scored, so very large companies (Freshworks, Postman)
can land in Tier A even though they'd be enterprise-sales accounts.
