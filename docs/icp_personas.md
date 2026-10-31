# ICP personas

Three ideal customer profiles for a payments SDR. Each one drives a column of weights in
[`config/icp.yaml`](../config/icp.yaml). A company is scored on the ICP that matches its vertical.

---

## 1. `d2c_growth`: D2C growth brand

**Who they are.** Indian consumer brands selling on their own website, mostly on Shopify or
WooCommerce. They usually also sell on Amazon and Nykaa but own their customer on the website.
Beauty, apparel, food and nutrition dominate. Typically 1–8 years old, often venture-funded.

**Typical payment pain**
- Failed payments at checkout during sale spikes (one gateway goes down → lost orders).
- High cash-on-delivery (COD) share → returns, RTO costs and slow cash.
- Refund speed hurts ratings and repeat purchases.

**Buyer.** Founder, Head of Growth, or Head of E-commerce. The CFO joins after Series A.

**Products that fit.** Payment Gateway (as primary or backup route), checkout-conversion
features, Payment Links to nudge COD buyers to prepaid, fast refunds.

**Why the weights look like this**

| Signal | Weight | Reason |
|---|---|---|
| Competitor gateway (high/medium) | +20 | We know what to displace, or where a second route fits |
| Single gateway | +10 | The backup-route pitch is concrete and low-risk for them |
| Recent funding (≤18 mo) | +20 | Funding means growth plans, volume and budget |
| Shopify / WooCommerce | +10 | Plugin integration: short sales cycle |
| Paid checkout layer (GoKwik, Shopflo…) | +10 | They already pay to improve conversion |
| Subscriptions, International | +10 each | Extra products to sell |
| COD, Mobile app, Public email | +5 each | Smaller nudges |
| Already on Cashfree | −30 | Account manager's job, not SDR's |

---

## 2. `edtech_subscription`: Edtech with recurring fees

**Who they are.** Test-prep, K-12, upskilling and study-abroad companies that charge course fees,
often monthly or in instalments. Many sell through an app as much as the website.

**Typical payment pain**
- Recurring fees and EMIs: failed renewals and manual follow-ups.
- Large one-time course fees that need EMI / pay-later options.
- Collecting fees through counsellors (payment links over WhatsApp).

**Buyer.** Founder, CFO, or Head of Product / Growth.

**Products that fit.** Subscriptions (UPI Autopay / e-mandate), Payment Links, Payment Gateway.

**Why the weights look like this.** Subscription is the strongest signal (+25) because recurring
collection is the core pain. A mobile app (+10) means in-app payments and volume. Platform and COD
don't matter here (0).

---

## 3. `saas_global`: Indian SaaS selling abroad

**Who they are.** Software companies built in India that sell to customers in the US, Europe and
the Middle East, usually priced in USD with monthly or annual plans.

**Typical payment pain**
- Collecting international card payments and settling them into India.
- FX costs, purpose codes, FIRC paperwork and compliance.
- Failed recurring card charges (dunning).

**Buyer.** CFO or Head of Finance. Sometimes the founder at early stages.

**Products that fit.** Cross-border collections, Payment Gateway, Subscriptions. Payouts for
partner or affiliate commissions.

**Why the weights look like this.** International (+30) is the whole pitch, so it carries the
most weight. Subscriptions (+20) come next. Gateway signals matter less (+10) because many SaaS
companies bill through Stripe or Chargebee, and the conversation is about cross-border rather
than replacing a gateway.
