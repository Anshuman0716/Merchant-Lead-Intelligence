import pytest

from leadintel.openers import TEMPLATES, make_opener

CTX = {"gateways": ["razorpay"], "layer": "gokwik", "funding_stage": "A"}
LONG_NAME = "Two Brothers Organic Farms"


@pytest.mark.parametrize("signal", [*TEMPLATES, None, "unknown_signal"])
def test_opener_rules(signal):
    text = make_opener(LONG_NAME, signal, CTX)
    assert LONG_NAME in text
    assert text.endswith("?")
    assert len(text.split()) < 30
    assert text.count("?") == 1  # one sentence, one question


def test_fills_gateway_layer_and_stage():
    assert "Razorpay" in make_opener("Brand", "single_gateway", CTX)
    assert "GoKwik" in make_opener("Brand", "checkout_layer", CTX)
    assert "Series A" in make_opener("Brand", "recent_funding", CTX)


def test_missing_detail_falls_back_to_default():
    text = make_opener("Brand", "single_gateway", {"gateways": []})
    assert text == TEMPLATES["default"].format(name="Brand")


def test_no_false_claims():
    for signal in TEMPLATES:
        text = make_opener("Brand", signal, CTX).lower()
        assert "is low" not in text and "failing" not in text
