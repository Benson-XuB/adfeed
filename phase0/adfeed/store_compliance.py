"""Lightweight Shopify storefront compliance scan (GMC Misrepresentation prep).

Uses Admin policies.json + quick HTTPS/contact probes. Does not crawl full site.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx

from .market_pricing import PreflightStatus, expected_currency_for_country, preflight_country

logger = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(
    r"lorem ipsum|placeholder|\[your store\]|\[business name\]|xxx@|example\.com",
    re.I,
)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TEL_RE = re.compile(r"tel:\+?\d|\+?\d[\d\s\-()]{7,}\d")

_POLICY_SPECS = (
    ("POL_REFUND", "refund", "Refund policy", "Settings → Policies → Refund policy"),
    ("POL_PRIVACY", "privacy", "Privacy policy", "Settings → Policies → Privacy policy"),
    ("POL_SHIPPING", "shipping", "Shipping policy", "Settings → Policies → Shipping policy"),
    ("POL_TERMS", "terms", "Terms of service", "Settings → Policies → Terms of service"),
)

_HREF_RE = re.compile(r"""href\s*=\s*["']([^"'#][^"']*)["']""", re.I)
_FOOTER_RE = re.compile(r"<footer\b[^>]*>(.*?)</footer>", re.I | re.DOTALL)

_FOOTER_POLICY_PATTERNS: dict[str, tuple[str, ...]] = {
    "refund": ("/policies/refund", "refund-policy", "refund_policy"),
    "privacy": ("/policies/privacy", "privacy-policy"),
    "shipping": ("/policies/shipping", "shipping-policy"),
    "terms": ("/policies/terms", "terms-of-service", "terms-of-service"),
}

_FOOTER_CONTACT_PATTERNS = (
    "/pages/contact",
    "/pages/contact-us",
    "contact-us",
    "/pages/about",
)


@dataclass
class ComplianceCheck:
    id: str
    status: str  # pass | warn | unknown
    message: str
    suggestion: str = ""
    fix_admin_path: str = ""


@dataclass
class StoreComplianceReport:
    light: str = "green"
    checks: list[ComplianceCheck] = field(default_factory=list)
    shop_currency: str = ""
    site_url: str = ""
    countries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        counts = {"pass": 0, "warn": 0, "unknown": 0}
        for c in self.checks:
            key = c.status if c.status in counts else "warn"
            counts[key] = counts.get(key, 0) + 1
        return {
            "light": self.light,
            "summary": counts,
            "shop_currency": self.shop_currency,
            "site_url": self.site_url,
            "countries": self.countries,
            "checks": [
                {
                    "id": c.id,
                    "status": c.status,
                    "message": c.message,
                    "suggestion": c.suggestion,
                    "fix_admin_path": c.fix_admin_path,
                }
                for c in self.checks
            ],
        }


def _shop_host(shop_domain: str) -> str:
    shop = (shop_domain or "").replace("https://", "").replace("http://", "").strip().lower()
    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"
    return shop


def _admin_url(shop_domain: str, path: str) -> str:
    return f"https://{_shop_host(shop_domain)}/admin{path}"


def _normalize_site_url(site_url: str, shop_domain: str) -> str:
    url = (site_url or "").strip()
    if not url:
        url = f"https://{_shop_host(shop_domain)}"
    if not url.startswith("http"):
        url = f"https://{url}"
    return url.rstrip("/")


def _policy_kind(policy: dict) -> Optional[str]:
    """Map Shopify policy row to refund|privacy|shipping|terms."""
    handle = str(policy.get("handle") or "").lower()
    url = str(policy.get("url") or "").lower()
    title = str(policy.get("title") or "").lower()
    blob = f"{handle} {url} {title}"
    if "refund" in blob or "return" in blob:
        return "refund"
    if "privacy" in blob:
        return "privacy"
    if "shipping" in blob:
        return "shipping"
    if "terms" in blob or "service" in blob:
        return "terms"
    return None


def _body_quality(body: str) -> tuple[str, str]:
    """Return (status, detail) for policy body."""
    text = (body or "").strip()
    if len(text) < 80:
        return "warn", "Policy body is too short or empty — expand it"
    if _PLACEHOLDER_RE.search(text):
        return "warn", "Looks like placeholder/template text — replace with your real policy"
    return "pass", "Policy is filled in"


def fetch_shopify_policies(shop_domain: str, access_token: str) -> tuple[list[dict], bool]:
    try:
        from .shopify_admin_gql import fetch_policies
        return fetch_policies(shop_domain, access_token)
    except Exception as e:
        logger.warning("fetch policies failed: %s", e)
        return [], False


def fetch_shop_snapshot(shop_domain: str, access_token: str) -> dict:
    try:
        from .shopify_admin_gql import fetch_shop
        return fetch_shop(shop_domain, access_token)
    except Exception as e:
        logger.warning("shop snapshot GraphQL failed: %s", e)
        return {}


def _probe_url(url: str) -> tuple[int, str]:
    try:
        with httpx.Client(timeout=8, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "AdFeed-Compliance/1.0"})
            return resp.status_code, resp.text[:8000]
    except Exception:
        return 0, ""


def _has_contact_signals(html: str) -> bool:
    if not html:
        return False
    if _EMAIL_RE.search(html):
        return True
    if _TEL_RE.search(html):
        return True
    low = html.lower()
    return "contact-form" in low or 'type="email"' in low


def _extract_footer_html(html: str) -> str:
    if not html:
        return ""
    m = _FOOTER_RE.search(html)
    return m.group(1) if m else ""


def _normalize_href(href: str, base_url: str) -> str:
    h = (href or "").strip()
    if not h or h.startswith(("javascript:", "mailto:", "tel:")):
        return ""
    if h.startswith("//"):
        h = "https:" + h
    if h.startswith("http"):
        parsed = urlparse(h)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        return path.lower()
    return urljoin(base_url + "/", h.lstrip("/")).lower()


def _extract_hrefs(html: str, base_url: str) -> set[str]:
    out: set[str] = set()
    if not html:
        return out
    for m in _HREF_RE.finditer(html):
        norm = _normalize_href(m.group(1), base_url)
        if norm:
            out.add(norm)
    return out


def _policy_linked(
    policy_url: str,
    kind: str,
    hrefs: set[str],
    html_blob: str,
) -> bool:
    """True if policy appears linked in href set or raw HTML."""
    blob = (html_blob or "").lower()
    path = urlparse(policy_url).path.lower() if policy_url else ""
    if path and (path in hrefs or path in blob):
        return True
    for pat in _FOOTER_POLICY_PATTERNS.get(kind, ()):
        if any(pat in h for h in hrefs) or pat in blob:
            return True
    return False


def _contact_linked(hrefs: set[str], html_blob: str) -> bool:
    blob = (html_blob or "").lower()
    for pat in _FOOTER_CONTACT_PATTERNS:
        if any(pat in h for h in hrefs) or pat in blob:
            return True
    return False


_CONTACT_PATHS = (
    "/pages/contact",
    "/pages/contact-us",
    "/pages/contactus",
    "/pages/about",
    "/pages/about-us",
)


def diagnose_store_compliance(
    *,
    shop_domain: str,
    access_token: str,
    site_url: str = "",
    shop_currency: str = "USD",
    countries: Optional[list[str]] = None,
) -> StoreComplianceReport:
    """Run lite compliance checks; never raises."""
    countries = [c.upper() for c in (countries or ["US"]) if c]
    report = StoreComplianceReport(
        shop_currency=(shop_currency or "USD").upper(),
        site_url=_normalize_site_url(site_url, shop_domain),
        countries=countries,
    )
    checks: list[ComplianceCheck] = []

    # ── Policies (Admin API) ──
    policies, policies_readable = fetch_shopify_policies(shop_domain, access_token)
    found: dict[str, dict] = {}
    for p in policies:
        kind = _policy_kind(p)
        if kind:
            found[kind] = p

    if not policies_readable:
        checks.append(ComplianceCheck(
            id="POL_SCAN",
            status="unknown",
            message="Could not read Shopify policies via the app (missing read_legal_policies scope)",
            suggestion="Check Settings → Policies manually in Shopify Admin — this alone does not mean Google will disapprove",
            fix_admin_path="/settings/legal",
        ))
    else:
        for check_id, kind, label, admin_hint in _POLICY_SPECS:
            p = found.get(kind)
            if not p:
                checks.append(ComplianceCheck(
                    id=check_id,
                    status="warn",
                    message=f"Missing {label}",
                    suggestion=f"Create and publish it in Shopify {admin_hint}",
                    fix_admin_path="/settings/legal",
                ))
                continue
            st, detail = _body_quality(str(p.get("body") or ""))
            pub_url = str(p.get("url") or "")
            msg = f"{label}: {detail}"
            if pub_url:
                msg += f" ({pub_url})"
            checks.append(ComplianceCheck(
                id=check_id,
                status=st,
                message=msg,
                suggestion="Link this policy from the footer menu" if st != "pass" else "",
                fix_admin_path="/settings/legal",
            ))

    # ── HTTPS + homepage reachable ──
    site = report.site_url
    if site.startswith("https://"):
        checks.append(ComplianceCheck(
            id="SITE_HTTPS",
            status="pass",
            message="Store URL uses HTTPS",
        ))
    else:
        checks.append(ComplianceCheck(
            id="SITE_HTTPS",
            status="warn",
            message="Store URL is not HTTPS",
            suggestion="Use a custom domain with SSL in Shopify",
        ))

    code, home_html = _probe_url(site)
    footer_html = _extract_footer_html(home_html)
    footer_hrefs = _extract_hrefs(footer_html, site) if footer_html else set()
    page_hrefs = _extract_hrefs(home_html, site)

    if code == 200:
        checks.append(ComplianceCheck(
            id="SITE_REACHABLE",
            status="pass",
            message="Homepage is reachable",
        ))
    elif code:
        checks.append(ComplianceCheck(
            id="SITE_REACHABLE",
            status="warn",
            message=f"Homepage returned HTTP {code}",
            suggestion="Confirm the store is not password-protected and the domain is publicly reachable",
        ))
        home_html = ""
    else:
        checks.append(ComplianceCheck(
            id="SITE_REACHABLE",
            status="warn",
            message="Could not probe homepage (timeout or network error)",
            suggestion="Open the storefront in a browser to confirm",
        ))
        home_html = ""

    # ── Footer discoverability (homepage HTML only — lite) ──
    if home_html:
        scan_footer = footer_html or home_html
        scan_hrefs = footer_hrefs if footer_html else page_hrefs
        foot_label = "footer" if footer_html else "homepage (no <footer> tag found)"

        for check_id, kind, label, _admin_hint in _POLICY_SPECS:
            p = found.get(kind)
            if not p:
                continue
            pub_url = str(p.get("url") or "")
            in_footer = _policy_linked(pub_url, kind, footer_hrefs, footer_html) if footer_html else False
            in_scan = _policy_linked(pub_url, kind, scan_hrefs, scan_footer)
            foot_id = check_id.replace("POL_", "FOOT_")
            if in_footer:
                checks.append(ComplianceCheck(
                    id=foot_id,
                    status="pass",
                    message=f"{label} is linked in the footer",
                    fix_admin_path="/menus",
                ))
            elif in_scan:
                checks.append(ComplianceCheck(
                    id=foot_id,
                    status="warn",
                    message=f"{label} is linked on the {foot_label} but not inside <footer>",
                    suggestion="Online Store → Navigation → Footer menu — add the policy link",
                    fix_admin_path="/menus",
                ))
            else:
                checks.append(ComplianceCheck(
                    id=foot_id,
                    status="warn",
                    message=f"{label} is configured but not linked on homepage/footer",
                    suggestion="Add the policy page to the Footer menu (GMC expects it to be discoverable)",
                    fix_admin_path="/menus",
                ))

        foot_contact = _contact_linked(footer_hrefs, footer_html) if footer_html else False
        scan_contact = _contact_linked(scan_hrefs, scan_footer)
        if foot_contact:
            checks.append(ComplianceCheck(
                id="FOOT_CONTACT",
                status="pass",
                message="Contact is linked in the footer",
                fix_admin_path="/menus",
            ))
        elif scan_contact:
            checks.append(ComplianceCheck(
                id="FOOT_CONTACT",
                status="warn",
                message=f"Contact is linked on the {foot_label} but not inside <footer>",
                suggestion="Add the Contact page to the Footer menu",
                fix_admin_path="/menus",
            ))
    elif code == 200:
        checks.append(ComplianceCheck(
            id="FOOT_SCAN",
            status="warn",
            message="Could not parse homepage HTML; skipped footer link checks",
        ))

    # ── Contact page probe ──
    contact_ok = False
    contact_url = ""
    for path in _CONTACT_PATHS:
        url = urljoin(site + "/", path.lstrip("/"))
        c_code, c_html = _probe_url(url)
        if c_code == 200 and _has_contact_signals(c_html):
            contact_ok = True
            contact_url = url
            break

    shop_info = fetch_shop_snapshot(shop_domain, access_token)
    shop_email = str(shop_info.get("email") or shop_info.get("customer_email") or "")
    shop_phone = str(shop_info.get("phone") or "")

    if contact_ok:
        checks.append(ComplianceCheck(
            id="CONTACT_PAGE",
            status="pass",
            message=f"Found contact page {contact_url}",
        ))
    elif shop_email or shop_phone:
        checks.append(ComplianceCheck(
            id="CONTACT_PAGE",
            status="warn",
            message="No /pages/contact found, but the store has email/phone in admin",
            suggestion="Create a Contact page and link it in the footer (GMC often checks visible contact info)",
            fix_admin_path="/pages",
        ))
    else:
        checks.append(ComplianceCheck(
            id="CONTACT_PAGE",
            status="warn",
            message="No Contact page and no visible contact details found",
            suggestion="Add a Contact page with email + phone or address, and put it in the footer menu",
            fix_admin_path="/pages",
        ))

    # ── Currency vs target markets (reuse preflight) ──
    for cu in countries:
        pf = preflight_country(
            shop_currency=report.shop_currency,
            country=cu,
            sample_presentment=None,
        )
        exp = expected_currency_for_country(cu)
        if pf.status == PreflightStatus.GREEN:
            checks.append(ComplianceCheck(
                id=f"CURR_{cu}",
                status="pass",
                message=f"{cu} market: shop currency {report.shop_currency} matches Feed target {exp} (or is usable)",
            ))
        else:
            checks.append(ComplianceCheck(
                id=f"CURR_{cu}",
                status="warn",
                message=pf.message or f"{cu} needs {exp}; shop currency is {report.shop_currency}",
                suggestion="Align Shopify Markets / presentment currency with the target market before generating the feed",
                fix_admin_path="/settings/markets",
            ))

    # ── Aggregate light (no red / no "errors" — suggestions only) ──
    if any(c.status == "warn" for c in checks):
        light = "yellow"
    else:
        light = "green"

    report.light = light
    report.checks = checks
    return report
