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
    "uses_cashfree": "Thank you for choosing Cashfree, {name}; would a short review of your "
    "payment success rates be useful this quarter?",
    "recent_funding": "Congratulations on the {stage} round at {name}; as volumes grow, would it "
    "help to review how your payment stack will scale?",
    "competitor_gateway": "I noticed {name} processes payments through {gateway}; would you be "
    "open to a short discussion on improving success rates and settlement times?",
    "single_gateway": "I noticed {name} relies on {gateway} alone; would a backup payment route "
    "for peak sale periods be worth a short discussion?",
    "checkout_layer": "I see {name} uses {layer} at checkout; how are you currently monitoring "
    "payment success rates behind it during high-traffic sales?",
    "subscription": "I noticed {name} offers subscription plans; how are failed renewals and "
    "recurring mandates managed today?",
    "international": "I noticed {name} serves customers overseas; how are you currently "
    "collecting and settling international payments?",
    "emi": "I noticed {name} offers EMI options; how are instalment collections and failed "
    "payments handled today?",
    "cod": "I noticed {name} offers cash on delivery; have you considered converting more COD "
    "orders to prepaid at checkout?",
    "mobile_app": "I noticed {name} has a mobile app; how satisfied are you with the in-app "
    "checkout experience today?",
    "default": "Could I ask how satisfied {name} is with its current online payment success rates?",
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
