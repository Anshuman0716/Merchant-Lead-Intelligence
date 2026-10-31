# Competitor analysis: payment gateways and checkouts in India

*Research from public sources, checked October 2026. The dashboard's **Competitor Landscape → Battlecards** tab shows the same profiles (from `config/competitors.yaml`) next to how often each competitor appears on the merchants we crawled.*

> **How to read this.** Pricing is the published or widely reported standard rate. Large merchants always negotiate. Anything marked *(reported)* comes from press or third-party write-ups, many of them written by rival vendors. Confirm it before you quote it to a prospect.

## 1. The market in one paragraph

India's payment-gateway market was worth about **US$2.1B in 2025** and is forecast to reach **~US$3.9B by 2032**. The top five players hold roughly 68% (MarkNtel, paid report). **Razorpay** is named the leader in every source. **PayU, Cashfree, PhonePe and Paytm** follow, but share estimates range widely, from 40% to 55%+ for Razorpay, so treat any single number with care. Three shifts matter for an SDR in 2026:

1. **Checkout layers are the new battleground in D2C.**
   - GoKwik, Razorpay Magic Checkout, Shopflo and Shiprocket Checkout sit in front of the gateway and influence which gateway the brand uses.
   - In our crawl of 935 sites, a checkout layer is visible on 27% of them (73% of Shopify brands). A gateway is visible on only 8%.
2. **Consolidation.**
   - PayU partnered with GoKwik (March 2026).
   - Pine Labs announced it is acquiring Shopflo (April 2026, reported).
   - Juspay became a unicorn (January 2026).
   - Razorpay filed confidential IPO papers (June 2026).
3. **UPI economics may change.** A return of MDR on large-merchant UPI is under active policy discussion. Any change shifts pricing pitches.

## 2. Competitor profiles

| Competitor | Type | Threat to us | Standard pricing (public) | Where they win | How we win |
|---|---|---|---|---|---|
| **Razorpay** | Gateway, market leader | High | 2% + GST, no setup or AMC; custom above ~₹5L/month | Startups, Shopify D2C, broad suite | Be the **second route**; success-rate and settlement data in sale spikes |
| **PayU** | Gateway, enterprise + SMB | High | ~2% domestic, ~3% international *(third-party)* | Enterprise, edtech, BFSI; GoKwik tie-up | Faster onboarding, modern APIs, UPI Autopay |
| **CCAvenue** | Legacy gateway | Medium | Plan-based, annual fee on some plans | Traditional businesses, institutes, travel | Better mobile checkout, no annual fee |
| **Paytm** | Wallet + gateway | Medium | UPI zero-MDR; cards ~1.99%+ | Consumer familiarity, offline QR | Reliable primary or backup with a clean compliance story |
| **PhonePe** | UPI app + gateway | Medium | No fee on UPI / RuPay debit; ~1.99% cards *(reported)* | UPI scale and zero-fee headline | Full stack: payouts, subscriptions, cross-border |
| **Juspay** | Orchestration | Medium | Enterprise contracts; open-source Hyperswitch | Large enterprises routing across gateways | Become a route inside Juspay, not a rival to it |
| **Easebuzz** | Vertical gateway (education) | Medium in edtech | Competitive MDR + fee-collection suite | Schools and colleges: instalments, reminders, eNACH | UPI Autopay, EMI and payouts in one stack |
| **Stripe** | Global gateway | Medium in SaaS | ~4.3% + ~2% FX for Indian sellers *(competitor estimate)* | SaaS billing global customers | Lower-cost cross-border collections, INR settlement; Stripe India is invite-only |
| **BillDesk** | Legacy enterprise | Low | Enterprise contracts | Utilities, insurance, government | Modern APIs for digital-first teams |
| **PayPal** | Global wallet | Low | ~4.4% + fixed fee on international receipts | Extra button for overseas buyers | Cross-border at lower cost |
| **Instamojo** | SMB payments | Low | ~2% + ₹3 | Creators, micro-businesses | Scaling features: routing, subscriptions |

### Checkout layers (D2C)

| Layer | Positioning | What it tells the SDR |
|---|---|---|
| **GoKwik** | RTO-focused one-click checkout for Shopify; partnered with PayU (March 2026) | The brand pays for conversion, so pitch a high-success-rate gateway behind it |
| **Razorpay Magic Checkout** | Razorpay's one-click checkout, built mainly for Razorpay's own gateway | Locked to one gateway, so pitch a backup route for sale days |
| **Shopflo** | Conversion and upsell checkout, supports multiple gateways; Pine Labs acquisition announced April 2026 *(reported)* | Multi-gateway by design, so Cashfree is easy to add |
| **Shiprocket Checkout** | Bundled with Shiprocket logistics | Pitch success rates and faster settlement |
| **Chargebee** | Subscription billing for SaaS, runs on top of gateways | Cashfree plugs in as a gateway for UPI Autopay and cross-border |

## 3. What our own crawl adds

The dashboard counts what is visible on each merchant's public pages. Use these counts together with the profiles above:

- **Gateway counts are a floor.** Most gateways load only at the final payment step, which we never reach because we don't log in or check out. The **Nothing visible** count is the share to discover on the call.
- **Single-gateway merchants** (mostly Razorpay, often through Magic Checkout) are the clearest **backup-route** pitch.
- **Checkout-layer users** are D2C brands that already spend money on conversion. They are usually the most receptive to success-rate arguments.
- **Edtech and SaaS show very little publicly.** For them, the signals are subscriptions, EMI and international pricing, not a visible gateway.

## 4. Sources

- Razorpay pricing: [Razorpay blog – payment gateway pricing explained](https://razorpay.com/blog/razorpay-payment-gateway-pricing-explained/), [cheapest payment gateway in India](https://razorpay.com/blog/cheapest-payment-gateway-in-india/)
- Razorpay financials and IPO: [PL India – 65% revenue jump in FY25](https://www.plindia.com/news/razorpay-posts-65-revenue-jump-in-fy25-as-ipo-preparations-advance/), [Business Today – confidential DRHP](https://www.businesstoday.in/amp/markets/ipo-corner/story/fintech-unicorn-razorpay-files-confidential-drhp-to-launch-its-ipo-check-details-537107-2026-06-16), [Angel One](https://www.angelone.in/news/ipos/razorpay-takes-first-step-towards-ipo-files-confidential-drhp-with-sebi)
- PayU pricing (third-party): [Techimply – gateway fees compared](https://www.techimply.com/blog/payment-gateway-fees-india), [Xflow – PayU international charges](https://www.xflowpay.com/blog/payu-international-payment-charges)
- Cashfree: [Cashfree – payment gateway charges](https://www.cashfree.com/ae/payment-gateway-charges/), [Inc42 – Cashfree FY26](https://inc42.com/buzz/cashfree-fy26-revenue-inches-closer-to-₹1000-cr-mark-loss-narrows/)
- Market size: [MarkNtel Advisors – India payment gateways market](https://www.marknteladvisors.com/press-release/india-payment-gateways-market-share), [Ken Research](https://www.kenresearch.com/industry-reports/india-payment-gateway-market-krod10648)
- Market share estimates (vary): [irpr.agency](https://irpr.agency/blog/top-upi-payment-gateways-india-comparison-2026), [geo.sig.ai – Razorpay](https://geo.sig.ai/brands/razorpay.md)
- Checkout layers: [Shopflo – compare](https://shopflo.com/compare) *(vendor)*, [Shopflo vs Razorpay Magic](https://shopflo.com/blog/shopflo-vs-razorpay-magic-checkout-which-one-is-best-for-you) *(vendor)*, [Wiser Review – Shopflo alternatives](https://wiserreview.com/blog/shopflo-alternatives/), [Inc42 – Shop Pay to India](https://inc42.com/buzz/shopify-to-bring-accelerated-checkout-service-shop-pay-to-india/)
- Juspay: [Inc42 – first unicorn of 2026](https://inc42.com/buzz/juspay-becomes-first-unicorn-of-2026-after-raising-50-mn), [Finextra – $60M Series D](https://www.finextra.com/newsarticle/45781/juspay-raises-60-million)
- PhonePe and UPI MDR: [PhonePe – gateway charges](https://business.phonepe.com/articles/payment-gateway-charges-in-india-complete-mdr-and-fee-breakdown), [All About Fintech – UPI MDR 2026](https://allaboutfintech.beehiiv.com/p/upi-mdr-2026-what-bill-no-150-actually-changes)
- Easebuzz: [Easebuzz – education](https://easebuzz.in/use-cases/education), [Easebuzz](https://easebuzz.in)
- Stripe in India: [EximPe – Stripe for India](https://eximpe.com/blog/psp/stripe-for-india-what-works-what-doesnt-and-where-global-merchants-lose-indian-customers) *(competitor)*, [Skydo – Stripe alternatives](https://www.skydo.com/compare/stripe-alternatives.md) *(competitor)*, [TechCrunch – Stripe and PayPal back Xflow](https://techcrunch.com/2026/02/23/stripe-paypal-ventures-bet-on-indias-xflow-to-fix-cross-border-b2b-payments/)
