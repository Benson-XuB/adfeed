"""Lite store website compliance scan."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adfeed.store_compliance import (
    _body_quality,
    _extract_hrefs,
    _has_contact_signals,
    _policy_kind,
    _policy_linked,
)


def test_policy_kind_maps_refund():
    assert _policy_kind({"handle": "refund-policy", "title": "Refund"}) == "refund"


def test_body_quality_short_is_warn():
    st, _ = _body_quality("short")
    assert st == "warn"


def test_body_quality_placeholder_is_warn():
    st, _ = _body_quality("A" * 100 + " lorem ipsum " + "B" * 50)
    assert st == "warn"


def test_has_contact_signals_email():
    assert _has_contact_signals('<a href="mailto:support@shop.com">Email</a>')


def test_policy_linked_from_footer_href():
    hrefs = {"/policies/refund-policy"}
    assert _policy_linked("https://demo.com/policies/refund-policy", "refund", hrefs, "")


def test_footer_checks_warn_when_policy_missing_from_homepage():
    policies = [
        {"handle": "refund-policy", "body": "x" * 120, "url": "https://s.com/policies/refund-policy"},
        {"handle": "privacy-policy", "body": "x" * 120, "url": "https://s.com/policies/privacy-policy"},
        {"handle": "shipping-policy", "body": "x" * 120, "url": "https://s.com/policies/shipping-policy"},
        {"handle": "terms-of-service", "body": "x" * 120, "url": "https://s.com/policies/terms-of-service"},
    ]
    home = "<html><body><footer><a href='/pages/contact'>Contact</a></footer></body></html>"

    def fake_probe(url):
        if url.rstrip("/") == "https://demo.com":
            return 200, home
        if url.endswith("/pages/contact"):
            return 200, '<form><input type="email"> support@shop.com </form>'
        return 404, ""

    with patch("adfeed.store_compliance.fetch_shopify_policies", return_value=(policies, True)), patch(
        "adfeed.store_compliance.fetch_shop_snapshot",
        return_value={"email": "shop@example.com"},
    ), patch("adfeed.store_compliance._probe_url", side_effect=fake_probe):
        from adfeed.store_compliance import diagnose_store_compliance
        report = diagnose_store_compliance(
            shop_domain="demo.myshopify.com",
            access_token="tok",
            site_url="https://demo.com",
            shop_currency="USD",
            countries=["US"],
        )
    foot_refund = [c for c in report.checks if c.id == "FOOT_REFUND"]
    assert foot_refund and foot_refund[0].status == "warn"
    foot_contact = [c for c in report.checks if c.id == "FOOT_CONTACT"]
    assert foot_contact and foot_contact[0].status == "pass"


def test_footer_checks_pass_when_policies_linked():
    policies = [
        {"handle": "refund-policy", "body": "x" * 120, "url": "https://s.com/policies/refund-policy"},
        {"handle": "privacy-policy", "body": "x" * 120, "url": "https://s.com/policies/privacy-policy"},
        {"handle": "shipping-policy", "body": "x" * 120, "url": "https://s.com/policies/shipping-policy"},
        {"handle": "terms-of-service", "body": "x" * 120, "url": "https://s.com/policies/terms-of-service"},
    ]
    home = """<html><footer>
      <a href="/policies/refund-policy">Refund</a>
      <a href="/policies/privacy-policy">Privacy</a>
      <a href="/policies/shipping-policy">Shipping</a>
      <a href="/policies/terms-of-service">Terms</a>
      <a href="/pages/contact">Contact</a>
    </footer></html>"""

    with patch("adfeed.store_compliance.fetch_shopify_policies", return_value=(policies, True)), patch(
        "adfeed.store_compliance.fetch_shop_snapshot", return_value={}
    ), patch("adfeed.store_compliance._probe_url", return_value=(200, home)):
        from adfeed.store_compliance import diagnose_store_compliance
        report = diagnose_store_compliance(
            shop_domain="demo.myshopify.com",
            access_token="tok",
            site_url="https://demo.com",
            shop_currency="USD",
            countries=["US"],
        )
    for kid in ("refund", "privacy", "shipping", "terms"):
        pass  # ids: FOOT_REFUND, FOOT_PRIVACY, FOOT_SHIPPING, FOOT_TERMS
    assert all(
        next(c for c in report.checks if c.id == fid).status == "pass"
        for fid in ("FOOT_REFUND", "FOOT_PRIVACY", "FOOT_SHIPPING", "FOOT_TERMS", "FOOT_CONTACT")
    )


def test_diagnose_policies_pass_with_mocks():
    policies = [
        {"handle": "refund-policy", "body": "x" * 120, "url": "https://s.com/policies/refund-policy"},
        {"handle": "privacy-policy", "body": "x" * 120, "url": "https://s.com/policies/privacy-policy"},
        {"handle": "shipping-policy", "body": "x" * 120, "url": "https://s.com/policies/shipping-policy"},
        {"handle": "terms-of-service", "body": "x" * 120, "url": "https://s.com/policies/terms-of-service"},
    ]

    def fake_probe(url):
        if url.rstrip("/") == "https://demo.com":
            return 200, """<footer>
              <a href="/policies/refund-policy">R</a>
              <a href="/policies/privacy-policy">P</a>
              <a href="/policies/shipping-policy">S</a>
              <a href="/policies/terms-of-service">T</a>
            </footer>"""
        if url.endswith("/pages/contact"):
            return 200, '<form><input type="email"> support@shop.com </form>'
            return 200, "<html>ok</html>"

    with patch("adfeed.store_compliance.fetch_shopify_policies", return_value=(policies, True)), patch(
        "adfeed.store_compliance.fetch_shop_snapshot",
        return_value={"email": "shop@example.com"},
    ), patch("adfeed.store_compliance._probe_url", side_effect=fake_probe):
        from adfeed.store_compliance import diagnose_store_compliance
        report = diagnose_store_compliance(
            shop_domain="demo.myshopify.com",
            access_token="tok",
            site_url="https://demo.com",
            shop_currency="USD",
            countries=["US"],
        )
    assert report.light in ("green", "yellow")
    ids = {c.id for c in report.checks}
    assert "POL_REFUND" in ids
    assert "CONTACT_PAGE" in ids
    assert "SITE_HTTPS" in ids
    assert any(c.id == "CONTACT_PAGE" and c.status == "pass" for c in report.checks)


def test_diagnose_currency_mismatch_warns():
    with patch("adfeed.store_compliance.fetch_shopify_policies", return_value=([], True)), patch(
        "adfeed.store_compliance.fetch_shop_snapshot", return_value={}
    ), patch("adfeed.store_compliance._probe_url", return_value=(200, "ok")):
        from adfeed.store_compliance import diagnose_store_compliance
        report = diagnose_store_compliance(
            shop_domain="demo.myshopify.com",
            access_token="tok",
            site_url="https://demo.com",
            shop_currency="CNY",
            countries=["US"],
        )
    curr = [c for c in report.checks if c.id == "CURR_US"]
    assert curr and curr[0].status == "warn"
    assert report.light != "red"
    assert not any(c.status == "fail" for c in report.checks)


def test_policies_unreadable_is_unknown_not_fail():
    with patch("adfeed.store_compliance.fetch_shopify_policies", return_value=([], False)), patch(
        "adfeed.store_compliance.fetch_shop_snapshot", return_value={}
    ), patch("adfeed.store_compliance._probe_url", return_value=(200, "ok")):
        from adfeed.store_compliance import diagnose_store_compliance
        report = diagnose_store_compliance(
            shop_domain="demo.myshopify.com",
            access_token="tok",
            site_url="https://demo.com",
            shop_currency="USD",
            countries=["US"],
        )
    assert report.light in ("green", "yellow")
    assert not any(c.status == "fail" for c in report.checks)
    pol_scan = [c for c in report.checks if c.id == "POL_SCAN"]
    assert pol_scan and pol_scan[0].status == "unknown"
    assert not any(c.id.startswith("POL_") and c.id != "POL_SCAN" for c in report.checks)
