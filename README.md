# Merchant Lead Intelligence Engine

> It tells a payments SDR which merchants to call first, why, and what to say.

Takes 300–500 Indian online businesses (D2C, edtech, SaaS), detects their payment setup from
public website signals, scores them against 3 ICPs, and outputs a tiered, CRM-ready lead list
with personalised openers — plus a dashboard and a one-page insight note.

🚧 Work in progress — Phases 0–2 done (universe, crawler, signal detection).

## How to run

```bash
make setup      # install deps
make pipeline   # rebuild everything from data/seeds/
make app        # open the dashboard
make test
```

Stages can be run alone: `uv run python -m leadintel.run --only crawl`, `--from detect`,
`--refresh` (re-fetch cached pages), `--limit 10`.

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
