# Merchant Lead Intelligence Engine — Project Guide

A complete walkthrough of what this project does, how it is built, how data flows through it,
how leads are scored into tiers, and what every part of the dashboard shows.

---

## 1. The main objective

**Problem.** A sales rep (SDR) at a payments company like Cashfree has to decide every day which
merchants to call. Before a call they research each merchant by hand: Which e-commerce platform
are they on? Which payment gateway do they use? Do they sell subscriptions or ship abroad? Most of
that research is slow, and many leads turn out to be a poor fit.

**Objective.** Automate that research using only public websites, and turn it into three answers
for every merchant:

1. **Who to call first** — a score from 0 to 100 and a tier (A / B / C).
2. **Why** — the top 3 reasons behind the score, in plain English, with evidence.
3. **What to say** — a one-line opening question, suggested products, and a BANT guess
   (Budget, Authority, Need, Timeline).

**Scope.** 1,072 Indian businesses across three verticals — D2C brands, edtech and SaaS — which
become 995 scored leads after cleaning.

---

## 2. Tech stack and how each piece is used

| Layer | Tool | What it does in this project |
|---|---|---|
| Language | **Python 3.12** | Everything is written in Python. |
| Package manager | **uv** | Creates the virtual environment and installs exact versions from `uv.lock`. |
| HTTP client | **httpx** (async) | Checks whether each website is reachable, and fetches pages concurrently. |
| Retries | **tenacity** | Retries a page fetch up to 2 times on network errors, with a 2-second wait. |
| HTML parsing | **selectolax** (Lexbor) | Very fast HTML parser. Pulls out script URLs, links, images and visible text from each page. |
| Robots rules | **urllib.robotparser** | Reads each site's `robots.txt` and skips pages the site doesn't allow bots to read. |
| Data frames | **Polars** | All data cleaning, joins and transformations in the pipeline. |
| Storage | **DuckDB** | One local database file (`data/leadintel.duckdb`). Each pipeline stage reads a table and writes a new one. |
| Data validation | **Pandera** | Every table has a schema (column types, allowed values, uniqueness). A stage fails loudly if its output is wrong. |
| Configuration | **YAML** (PyYAML) | Detection rules, scoring weights and crawler settings live in `config/*.yaml`, so they can be changed without touching code. |
| Export format | **Parquet** (pyarrow) | The final lead table is saved as `exports/leads.parquet`, which the dashboard reads. |
| Dashboard | **Streamlit** + **pandas** | The 4-page web app the SDR uses. |
| Charts | **Plotly** | Bar charts, histogram, heatmap and the score gauge. |
| Optional rendering | **Playwright** | A headless browser fallback for pages built entirely with JavaScript (off by default). |
| Testing | **pytest** | 99 tests that run offline using saved HTML pages. |
| Lint / format | **ruff** | Code style checks. |
| CI | **GitHub Actions** | Runs lint + tests on every push. |

---

## 3. Architecture

The project is a **6-stage batch pipeline** followed by a **dashboard**. Each stage reads one
DuckDB table, does one job, validates its output with Pandera, and writes the next table. Because
every stage's output is stored, any stage can be re-run on its own.

```
 data/seeds/*.csv
       │
       ▼
 ┌──────────┐   ┌─────────┐   ┌─────────┐   ┌──────────┐   ┌─────────┐   ┌──────────┐
 │  ingest  │ → │  clean  │ → │  crawl  │ → │  detect  │ → │  score  │ → │  export  │
 └──────────┘   └─────────┘   └─────────┘   └──────────┘   └─────────┘   └──────────┘
 raw_companies   companies       pages        signals      lead_scores     exports/
                                (+ HTML                                    leads.parquet
                                 cache)                                    hubspot_companies.csv
                                                                           leads_tier_A.csv
                                                                                 │
                                                                                 ▼
                                                                     Streamlit dashboard
```

**Folder layout**

```
config/        fingerprints.yaml (detection rules) · icp.yaml (scoring) · crawl.yaml (crawler)
data/seeds/    the input company lists: d2c.csv, edtech.csv, saas.csv
src/leadintel/ the pipeline: ingest, clean, crawl, detect, score, openers, export, schemas, db, run
app/           Home.py (navigation + sidebar) and views/ (the 4 dashboard pages)
exports/       pipeline outputs read by the app and by HubSpot
tests/         unit tests + saved HTML fixtures
docs/          ICP personas, cold emails, insight note, screenshots, this guide
```

**Running it**

```bash
make pipeline                                   # all 6 stages
uv run python -m leadintel.run --only crawl     # one stage
uv run python -m leadintel.run --from detect    # a stage and everything after it
make app                                        # open the dashboard
make test                                       # run the tests
```

---

## 4. How the data flows, stage by stage

### Stage 1 — Ingest (`ingest.py` → table `raw_companies`)

**Where the data comes from.** Three hand-built CSV files in `data/seeds/`, one per vertical. Each
row has: company name, website URL, vertical, sub-category, city, source, funding stage and last
funding date. The lists were drafted with help from an LLM and marked `llm_draft:verify`, then
checked during cleaning.

The ingest stage reads all three files, trims spaces, turns empty cells into nulls, lower-cases
the vertical, parses dates, and validates the result against the `RawCompanies` schema.
**Result: 1,072 rows.**

### Stage 2 — Clean (`clean.py` → table `companies`)

1. **Normalise the domain.** `HTTPS://www.Brand.in/shop?x=1` becomes `brand.in`.
2. **Remove duplicates.** One row per domain; if two rows disagree, keep the one with more fields
   filled in.
3. **Check reachability.** Sends one request to each homepage (20 at a time, 5-second timeout,
   with one slower retry for failures). Results are cached in `data/cache/reachability.json`.
4. **Quarantine bad rows instead of deleting them.** Each bad row stays in the table with
   `is_valid = False` and a reason:
   - `not_own_site` — the URL is a marketplace or social page (Amazon, Instagram…)
   - `duplicate_of:<domain>` — the site redirects to another company already in the list
   - `blocked_403` / `blocked_429`… — the site blocks bots (we respect this and don't bypass it)
   - `unreachable` / `http_404`… — the site is down or broken

**Result: 364 valid companies.** About 25 bot-blocked sites are still scored later, using only
their seed data.

### Stage 3 — Crawl (`crawl.py` → table `pages` + HTML cache)

For each valid company, a polite crawler fetches **up to 5 public pages**:

| Page | How it's found |
|---|---|
| home | the homepage (after redirects) |
| product | the first internal link containing `/products/`, `/product/`, `/course`, `/shop` or `/collections/` |
| cart | `/cart` |
| pricing | a `/pricing` or `/plans` link, or `/pricing` |
| contact | a `/contact` link, or `/contact`, `/contact-us`, `/pages/contact`… |

**Politeness rules:** reads `robots.txt` first and skips disallowed pages; waits at least 2 seconds
between requests to the same site; at most 10 sites at a time; an honest user agent that links to
the project; no logins, no forms, no checkout attempts.

Each page is saved gzip-compressed in `data/cache/html/<domain>/`, so later runs don't need the
internet. **Result: 1,221 pages from 362 sites.**

### Stage 4 — Detect (`detect.py` → table `signals`)

Each cached page is parsed into five searchable parts: **script** URLs and inline script code,
raw **html**, **links**, **images** (src/alt text), and visible **text**. Rules in
`config/fingerprints.yaml` are matched against these parts.

What gets detected for each company:

| Signal | Example rule |
|---|---|
| Platform | `cdn.shopify.com` in the HTML → Shopify; `wp-content/plugins/woocommerce` → WooCommerce; nothing → custom |
| Payment gateway(s) | `checkout.razorpay.com` script → Razorpay; `secure.payu.in` → PayU; `js.stripe.com` → Stripe… |
| Checkout layer | GoKwik, Razorpay Magic Checkout, Shiprocket Checkout, Shopflo |
| Subscriptions, international sales, COD, EMI | regex rules on visible text (e.g. "auto-renew", "ships worldwide", "cash on delivery", "no cost EMI") |
| Android / iOS app | links to Play Store / App Store |
| Pricing page | the pricing page returned 200 OK |
| Contact email | a role-based email (sales@, hello@, care@…) **on the company's own domain** only |

**Confidence levels for gateways.** The gateway usually loads only at the final payment step,
which can't be reached without buying something. So every detection records *how* it was found:

| Confidence | Meaning |
|---|---|
| **high** | The gateway's own script is on a public page (e.g. `checkout.razorpay.com`). |
| **medium** | A checkout layer known to run on that gateway (Razorpay Magic Checkout → Razorpay). |
| **low** | The gateway's name appears in text or a logo, **and** payment words are nearby. |

**False-positive protections learned from real pages:**
- "paypal" appears on every Shopify page as a built-in flag, so only the PayPal SDK URL counts.
- Paytm and PhonePe show up as UPI icons and promo text, so they only count from scripts.
- Edtech sites show Razorpay as a hiring-partner logo; founder bios say "CEO of Cashfree
  Payments". Low-confidence matches therefore need payment words nearby.
- A vendor's own website doesn't count as using its product (chargebee.com ≠ "uses Chargebee").

Every match is saved as **evidence** (which page, where on the page, which pattern, confidence),
and the dashboard shows it.

### Stage 5 — Score (`score.py` + `openers.py` → table `lead_scores`)

Covered in full in the next section. For each company it produces: score, tier, top 3 reasons,
BANT, suggested products, opener, and whether the data came from the website or seed only.

### Stage 6 — Export (`export.py` → `exports/`)

Joins companies + signals + scores into one table, adds readable labels (e.g. `razorpay_magic` →
"Razorpay Magic Checkout"), sorts by score, and writes:

- **`leads.parquet`** — everything the dashboard needs. It is committed to git, so the deployed
  app works without the database or HTML cache.
- **`hubspot_companies.csv`** — ready to import into HubSpot CRM as companies.
- **`leads_tier_A.csv`** — the call list for SDRs.

---

## 5. How scoring and tier categorisation work

### Step 1 — Pick the ICP by vertical

An ICP (Ideal Customer Profile) is the kind of customer that fits best. Each vertical has one:

| Vertical | ICP | Buyer | Base products |
|---|---|---|---|
| D2C | D2C growth brand | Founder / Head of Growth | Payment Gateway |
| Edtech | Edtech with recurring fees | Founder / CFO / Head of Product | Payment Gateway, Payment Links |
| SaaS | Indian SaaS selling abroad | CFO / Head of Finance | Cross-border Collections, Payment Gateway |

### Step 2 — Turn signals into true/false flags

| Flag | True when… |
|---|---|
| competitor_gateway | a non-Cashfree gateway was found at high or medium confidence |
| single_gateway | exactly one gateway was found, and it's a competitor |
| uses_cashfree | Cashfree was detected |
| checkout_layer | a paid checkout layer was found (but **not** one that already revealed the gateway, so one script isn't counted three times) |
| subscription / international / cod / emi | the feature was detected |
| recent_funding | last funding date within 18 months |
| shopify_woo | platform is Shopify or WooCommerce |
| mobile_app | Android or iOS app found |
| pricing_page | public pricing page exists |
| contact_email | public business email found |

### Step 3 — Add up the weights

**Score = sum of the weights of the true flags, clipped to 0–100.** Weights come from
`config/icp.yaml` and differ by ICP, because each signal matters differently per vertical:

| Signal | D2C | Edtech | SaaS |
|---|---|---|---|
| Competitor gateway | +20 | +15 | +10 |
| Single gateway | +10 | +10 | +5 |
| Already on Cashfree | −30 | −30 | −30 |
| Paid checkout layer | +10 | 0 | 0 |
| Subscriptions | +10 | **+25** | +20 |
| International sales | +10 | +5 | **+30** |
| Recent funding | +20 | +15 | +15 |
| Shopify / WooCommerce | +10 | 0 | 0 |
| EMI | +5 | +15 | 0 |
| Mobile app | +5 | +10 | 0 |
| COD | +5 | 0 | 0 |
| Pricing page | 0 | +5 | +5 |
| Public email | +5 | +5 | +5 |

### Step 4 — Assign the tier

| Tier | Rule | What the SDR should do |
|---|---|---|
| **A** | score ≥ 40 | Call this week |
| **B** | score 25–39 | Add to an email/call sequence |
| **C** | score < 25 | Low priority |
| **C (override)** | Cashfree detected | Existing customer → route to the account manager, never an SDR priority |

The thresholds were first A ≥ 65 / B ≥ 40, but with funding data still empty and gateways rarely
visible, only 2% of leads reached A. They were lowered to 40 / 25 after reviewing the leads.

**Current result:** Tier A 55 (14%) · Tier B 123 (32%) · Tier C 211 (54%).

| Vertical | A | B | C |
|---|---|---|---|
| D2C | 31 | 87 | 94 |
| Edtech | 1 | 10 | 78 |
| SaaS | 23 | 26 | 39 |

### Step 5 — Build the explanation

- **Reasons:** the true flags are sorted by weight, and the top 3 become plain-English reasons
  (templates in `icp.yaml`, e.g. *"Only one gateway detected (Razorpay) — pitch a backup route"*).
- **Suggested products:** the ICP's base products, plus extras from flags (subscription →
  "Subscriptions (UPI Autopay / e-mandate)", international → "Cross-border Collections", single
  gateway → "Payment Gateway (backup route)"…), max 3.
- **BANT:** Budget from funding stage (or "already pays for a checkout layer"), Authority from the
  ICP buyer, Need from the strongest flag, Timeline from recent funding.
- **Opener:** one question under 30 words, picked from the strongest reason. It never claims
  something the public pages don't show.

### Worked example — Livpure (D2C)

| Signal found | Weight |
|---|---|
| Razorpay via Razorpay Magic Checkout (medium) → competitor gateway | +20 |
| Only one gateway → single gateway | +10 |
| Checkout layer (Razorpay Magic already revealed the gateway, so not counted again) | 0 |
| Sells subscriptions | +10 |
| On Shopify | +10 |
| Offers EMI | +5 |
| Has Android/iOS app | +5 |
| Public email (customercare@livpure.com) | +5 |
| **Total** | **65 → Tier A** |

Opener: *"Noticed Livpure checks out via Razorpay — do you have a backup route for when it dips
during sale spikes?"*

---

## 6. The dashboard in detail

Start it with `make app` (or `uv run streamlit run app/Home.py`). `Home.py` sets up the page,
styling and sidebar, then hands off to one of four pages in `app/views/`.

### Look and feel

A light theme with an indigo primary colour, the Inter font, solid section headings with an
accent line, and KPI cards laid out in an equal-height grid so they always line up. Lead lists
are shown as rows (rank · company · why call · score · **Open** button) instead of wide
tables, so nothing needs sideways scrolling.

### Sidebar (on every page)

- **Merchant Lead Intelligence** heading, with the lead count and scoring date.
- **Prospecting**: Overview, Lead Explorer, Lead Detail.
- **Market**: Competitor Landscape.
- **Search for a company**: start typing and matching companies are suggested A → Z; pick one
  to open its brief from anywhere.
- **How tiers work**: the tier rules and what each tier means.

### Page 1 — Overview: *"How big is my opportunity?"*

| Section | What it shows |
|---|---|
| Header banner | Title, an accent line, and one sentence on what the tool does. |
| Quick actions | **Tier A call list** (opens Lead Explorer with Tier A selected), **Top lead brief**, **Competitors**. |
| Pipeline | Cards for total leads and Tier A / B / C (count, % and what to do), then two charts: leads by vertical and tier, and the score distribution with the tier cut-offs. |
| Payment stack | Cards for % of crawled sites with a visible gateway, a checkout layer, subscriptions and international sales, then charts of which gateways and checkout layers were seen. |
| Call these first | The top 10 Tier A leads (filter by vertical) as rows: rank, company with tier and vertical, why call, the opening line, score bar and an **Open** button. A *Last call* badge appears once the lead has been logged. |

### Page 2 — Lead Explorer: *"Who do I call today?"*

| Feature | What it does |
|---|---|
| Search for a company | Type-ahead: suggestions appear A → Z as you type. Pick one company, or press Enter on your text to match every company or domain that contains it. |
| Tier / Vertical buttons | Click one or more to filter. |
| Platform, Gateway, Checkout layer, City | Multi-select filters. |
| More filters and sorting | Sells subscriptions, sells internationally, has public email, hide sites we couldn't crawl, minimum score, funding known/unknown, and sort order. |
| Active-filter count + Reset | Shows how many filters are on; one click clears them all. |
| **Filters are remembered** | Open a lead and come back; your filters are still there. |
| Results | Leads shown, Tier A in view, average score, leads with a public email. |
| Lead list | 15 leads per page as rows (company, tier, vertical, platform, city, why call, payment stack, score, **Open**), with Previous / Next. |
| Download | Exports exactly the leads currently shown as a CSV. |

### Page 3 — Lead Detail: *"Who is this, and what do I say?"*

| Feature | What it shows |
|---|---|
| Lead picker + Previous / Next | Choose any lead, or step through them in score order. |
| Company profile | Name, tier badge and meaning, rank, ICP, a score box, and a fact grid: company, website link, domain, city, vertical, category, platform, funding. |
| Shareable link | The URL updates to `/Lead_Detail?domain=livpure.com` so a brief can be sent to a teammate. |
| Warning | Shown when the site blocks bots, so the score uses seed data only. |
| **Call brief tab** | *Why this lead* (3 numbered reasons), *What to pitch*, a *Contact information* card (email, website, who to ask for, location), a formal *Opening line*, and **BANT** cards: the public guess, the question to ask, and the latest verified status from the SDR log. |
| **SDR log tab** | A form to log each call: SDR name, outcome, follow-up date, a status (Not verified / Confirmed / Partly / Not a fit) and notes for each BANT section, next step and notes. Saved to `data/sdr/call_log.csv`; the full call history is listed below the form. |
| **Signals and evidence tab** | Every signal with its value and **where it was found**, e.g. *script "checkout.razorpay.com" on home page · high confidence*. |

### Page 4 — Competitor Landscape: *"Who am I up against, and how do I win?"*

| Feature | What it shows |
|---|---|
| Vertical switch | All verticals, D2C, Edtech or SaaS. |
| Headline cards | Sites with a gateway visible, a checkout layer visible, a single gateway (backup-route pitch), and nothing visible. |
| Tab: Battlecards | Pick a competitor (Razorpay, PayU, CCAvenue, Paytm, PhonePe, Juspay, Easebuzz, Stripe…): positioning, threat level, published pricing, strengths, weaknesses, **how we win**, how many crawled merchants use it, and the best Tier A/B leads on it. Also cards for each checkout layer and market notes. Research and sources: [competitor_analysis.md](competitor_analysis.md). |
| Tab: Gateways and checkout layers | Bar charts of what was found and on what % of sites, plus evidence by confidence. |
| Tab: Competitor × vertical | Heatmap of where each competitor appears, also as a table. |
| Tab: E-commerce platforms | Shopify / WooCommerce / Magento / custom by vertical. |

---

## 7. Key findings

1. **In D2C, the checkout layer is the battleground, not the gateway.** 73% of Shopify brands run a
   third-party checkout; GoKwik alone is on 29% of D2C sites.
2. **Where a gateway is visible, it's mostly Razorpay** (63 of 77). 72 merchants show a
   single gateway — a direct fit for the backup-route pitch.
3. **Edtech is nearly invisible on the public web.** Only 4 of 196 sites show subscription pricing,
   so this vertical needs other research (app stores, counsellors).

## 8. Limitations

- Gateway detection is a floor: most gateways load only at the payment step.
- Funding data isn't filled in yet; it's worth 15–20 points, so tiers will shift when it is.
- Company size isn't scored, so large enterprises can reach Tier A.
- The seed list is hand-built and not a representative sample of all Indian merchants.
