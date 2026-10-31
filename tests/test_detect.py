"""Detector tests on saved HTML fixtures (no internet).

Fixtures in tests/fixtures/html are minimal reproductions of patterns seen on real cached
merchant pages, plus traps that must NOT match (Shopify's built-in PayPal flag, UPI-app promo
names, "striped", "cod liver oil", newsletter "subscribe").
"""

from pathlib import Path

import pytest

from leadintel.detect import detect_domain, extract_contact_email
from leadintel.htmlparse import parse_page
from leadintel.settings import load_config

FIX = Path(__file__).parent / "fixtures" / "html"
RULES = load_config("fingerprints")


def detect(fixture: str, page_type: str = "home", domain: str = "brand.in"):
    html = (FIX / fixture).read_text(encoding="utf-8")
    pages = {page_type: parse_page(html, f"https://{domain}/")}
    return detect_domain(domain, pages, RULES)


@pytest.mark.parametrize(
    "fixture,platform",
    [
        ("shopify_gokwik.html", "shopify"),
        ("shopify_razorpay_magic.html", "shopify"),
        ("woocommerce_razorpay.html", "woocommerce"),
        ("magento_payu.html", "magento"),
        ("custom_cashfree.html", "custom"),
        ("plain.html", "custom"),
    ],
)
def test_platform(fixture, platform):
    assert detect(fixture).platform == platform


@pytest.mark.parametrize(
    "fixture,gateways,confidence,layer",
    [
        ("shopify_gokwik.html", [], None, "gokwik"),
        ("shopify_razorpay_magic.html", ["razorpay"], "medium", "razorpay_magic"),
        ("woocommerce_razorpay.html", ["razorpay"], "high", None),
        ("magento_payu.html", ["payu"], "high", None),
        ("custom_cashfree.html", ["cashfree"], "high", None),
        ("saas_stripe_usd.html", ["stripe"], "high", "chargebee"),
        ("footer_logo_ccavenue.html", ["ccavenue"], "low", None),
    ],
)
def test_gateway_and_confidence(fixture, gateways, confidence, layer):
    s = detect(fixture)
    assert s.gateways_detected == gateways
    assert s.gateway_confidence == confidence
    assert s.checkout_layer == layer


def test_plain_page_detects_nothing():
    s = detect("plain.html")
    assert s.gateways_detected == []
    assert s.checkout_layer is None
    assert not (s.has_subscription or s.has_cod or s.has_international)
    assert not (s.has_android_app or s.has_ios_app)


def test_upi_icons_and_shopify_paypal_are_not_gateways():
    s = detect("shopify_gokwik.html")
    assert "paytm" not in s.gateways_detected
    assert "phonepe" not in s.gateways_detected
    assert "paypal" not in s.gateways_detected


@pytest.mark.parametrize(
    "fixture,attr",
    [
        ("shopify_gokwik.html", "has_cod"),
        ("magento_payu.html", "has_cod"),
        ("shopify_razorpay_magic.html", "has_subscription"),
        ("custom_cashfree.html", "has_subscription"),
        ("saas_stripe_usd.html", "has_subscription"),
        ("saas_stripe_usd.html", "has_international"),
        ("woocommerce_razorpay.html", "has_international"),
        ("custom_cashfree.html", "has_android_app"),
        ("custom_cashfree.html", "has_ios_app"),
    ],
)
def test_features(fixture, attr):
    assert getattr(detect(fixture), attr) is True


def test_evidence_records_page_and_match():
    s = detect("woocommerce_razorpay.html")
    ev = s.evidence["gateway:razorpay"]
    assert ev["page"] == "home"
    assert ev["match"] == "checkout.razorpay.com"
    assert ev["level"] == "high"


@pytest.mark.parametrize(
    "body,expected",
    [
        ("<p>Payment partners : Razorpay PayU</p>", ["payu", "razorpay"]),
        ("<p>For COD returns, a Cashfree payment link will be sent.</p>", ["cashfree"]),
        ("<p>Madhuri, associate analyst, Razorpay. Before: XL Dynamics</p>", []),
        ("<p>Akash Sinha, CEO of Cashfree Payments</p>", []),
        ('<img alt="akash sinha - ceo and founder of cashfree payments">', []),
        ('<img src="/hiringpartners/ccavenue.png"><img alt="Razorpay logo">', []),
        ('<img src="/img/payment-icons/ccavenue.svg">', ["ccavenue"]),
    ],
)
def test_low_confidence_needs_payment_context(body, expected):
    page = parse_page(f"<html><body>{body}</body></html>", "https://brand.in/")
    s = detect_domain("brand.in", {"home": page}, RULES)
    assert s.gateways_detected == expected


def test_vendor_site_does_not_match_its_own_rule():
    s = detect("saas_stripe_usd.html", domain="chargebee.com")
    assert s.checkout_layer is None
    assert s.gateways_detected == ["stripe"]


def test_no_pages_means_unknown():
    s = detect_domain("brand.in", {}, RULES)
    assert s.platform == "unknown" and s.pages_crawled == 0


def test_contact_email_only_role_based_on_own_domain():
    html = (FIX / "contact.html").read_text(encoding="utf-8")
    pages = {"contact": parse_page(html, "https://brand.in/contact")}
    prefixes = RULES["contact_email_prefixes"]
    # partnerships@ ranks above support@; personal and off-domain addresses are never chosen
    assert extract_contact_email(pages, ["brand.in"], prefixes) == "partnerships@brand.in"
    assert extract_contact_email(pages, ["unrelated.in"], prefixes) is None
