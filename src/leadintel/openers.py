"""Template-based openers, chosen by the strongest scoring reason.

Rules: one sentence, under 30 words, contains the company name, ends with "?", and makes no
claim we can't back up from public pages (never "your success rate is low").
"""

from __future__ import annotations

GATEWAY_NAMES = {
    "razorpay": "Razorpay", "payu": "PayU", "cashfree": "Cashfree", "stripe": "Stripe",
    "paytm": "Paytm", "phonepe": "PhonePe", "ccavenue": "CCAvenue", "juspay": "Juspay",
    "easebuzz": "Easebuzz", "billdesk": "BillDesk", "paypal": "PayPal", "instamojo": "Instamojo",
    "paddle": "Paddle", "zaakpay": "Zaakpay",
}  # fmt: skip
LAYER_NAMES = {
    "gokwik": "GoKwik", "razorpay_magic": "Razorpay Magic Checkout",
    "shiprocket": "Shiprocket Checkout", "shopflo": "Shopflo", "chargebee": "Chargebee",
}  # fmt: skip
STAGE_NAMES = {"seed": "seed", "A": "Series A", "B+": "Series B+", "bootstrapped": "latest"}

TEMPLATES = {
    "uses_cashfree": "Thanks for building on Cashfree, {name} — would a quick review of your "
    "payment success rates be useful this quarter?",
    "recent_funding": "Congrats on the {stage} round at {name} — as volume scales, is payment "
    "success rate on your radar yet?",
    "competitor_gateway": "Noticed {name} checks out via {gateway} — do you have a backup route "
    "for when it dips during sale spikes?",
    "single_gateway": "Noticed {name} checks out via {gateway} — do you have a backup route for "
    "when it dips during sale spikes?",
    "checkout_layer": "Saw {name} uses {layer} for checkout — how are you tracking payment "
    "success rates behind it during sales?",
    "subscription": "Saw {name} offers subscription plans — curious how you handle failed "
    "renewals today?",
    "international": "Saw {name} sells to overseas customers — how are you collecting and "
    "settling those international payments right now?",
    "emi": "Saw {name} offers EMI options — how are you handling instalment collections and "
    "failed payments today?",
    "cod": "Saw {name} offers cash on delivery — have you tried nudging COD buyers to prepaid "
    "at checkout?",
    "mobile_app": "Saw {name} has a mobile app — how smooth is in-app checkout for your users "
    "today?",
    "default": "Quick question for {name} — how happy are you with your online payment success "
    "rates today?",
}


def make_opener(name: str, top_signal: str | None, ctx: dict) -> str:
    """Build the opener from the strongest contributing signal (falls back to a generic one)."""
    template = TEMPLATES.get(top_signal or "", TEMPLATES["default"])
    gateways = ctx.get("gateways") or []
    values = {
        "name": name,
        "gateway": GATEWAY_NAMES.get(gateways[0], gateways[0].title()) if gateways else "",
        "layer": LAYER_NAMES.get(ctx.get("layer") or "", ctx.get("layer") or ""),
        "stage": STAGE_NAMES.get(ctx.get("funding_stage") or "", "latest"),
    }
    if ("{gateway}" in template and not values["gateway"]) or (
        "{layer}" in template and not values["layer"]
    ):
        template = TEMPLATES["default"]
    return template.format(**values)
