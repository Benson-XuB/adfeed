"""Classify Merchant issues into ACCOUNT / FEED / MIXED for the narrow diagnostic UI."""

from __future__ import annotations

from typing import Any

# Codes (substring match on lowercased reason_code) treated as account-level.
_ACCOUNT_MARKERS = (
    "policy_enforcement_account",
    "account_disapproval",
    "account_suspend",
    "account_level",
    "shopping_ads_disabled",
    "merchant_suspended",
)

# Codes → human “common problem” buckets for feed/product data.
_FEED_BUCKETS: tuple[tuple[str, str], ...] = (
    ("title", "Product title"),
    ("brand", "Brand"),
    ("gtin", "Product identifiers"),
    ("upc", "Product identifiers"),
    ("mpn", "Product identifiers"),
    ("identifier", "Product identifiers"),
    ("image", "Images"),
    ("color", "Color / size / variants"),
    ("size", "Color / size / variants"),
    ("attribute", "Required attributes"),
    ("description", "Description"),
    ("price", "Price / availability"),
    ("availability", "Price / availability"),
)


def bucket_for_code(code: str) -> str:
    """Return 'account', 'feed', or 'other'."""
    key = (code or "").strip().lower()
    if any(m in key for m in _ACCOUNT_MARKERS):
        return "account"
    for marker, _label in _FEED_BUCKETS:
        if marker in key:
            return "feed"
    # Unknown product-ish defaults: treat as feed-ish so we don't hide catalog work
    if key and key != "unknown":
        return "feed"
    return "other"


def feed_problem_label(code: str) -> str | None:
    key = (code or "").strip().lower()
    for marker, label in _FEED_BUCKETS:
        if marker in key:
            return label
    if bucket_for_code(code) == "feed":
        return "Other product data"
    return None


def classify_issues(issues: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Return a narrow diagnostic payload:
      issue_type: ACCOUNT | FEED | MIXED | NONE
      likely_* copy fields, counts, common_problems (no product rows)
    """
    total = len(issues)
    if total == 0:
        return {
            "issue_type": "NONE",
            "label": "No disapprovals in this sample",
            "headline": "No disapprovals in this sample.",
            "what_this_means": [
                "We didn’t see disapproved / not-eligible products in this pull.",
                "If Merchant Center still shows problems, check there directly.",
            ],
            "what_you_should_do": [
                "Open Merchant Center and confirm product status",
                "Or run the free Feed Checker on your public feed URL",
            ],
            "adfeed_can_help": False,
            "cta": "feed_checker",
            "affected_count": 0,
            "signal_count": 0,
            "account_signal_count": 0,
            "feed_signal_count": 0,
            "unique_offer_count": 0,
            "feed_offer_count": 0,
            "account_offer_count": 0,
            "account_share": 0.0,
            "feed_share": 0.0,
            "common_problems": [],
            "disclaimer": (
                "Likely issue type from Merchant API signals — not Google’s official "
                "root-cause label or policy name."
            ),
        }

    account_n = 0
    feed_n = 0
    problem_counts: dict[str, int] = {}
    all_offers: set[str] = set()
    feed_offers: set[str] = set()
    account_offers: set[str] = set()
    for iss in issues:
        code = str(iss.get("reason_code") or "")
        oid = str(iss.get("offer_id") or "").strip()
        if oid:
            all_offers.add(oid)
        kind = bucket_for_code(code)
        if kind == "account":
            account_n += 1
            if oid:
                account_offers.add(oid)
        elif kind == "feed":
            feed_n += 1
            if oid:
                feed_offers.add(oid)
            label = feed_problem_label(code)
            if label:
                problem_counts[label] = problem_counts.get(label, 0) + 1
        else:
            pass

    account_share = account_n / total
    feed_share = feed_n / total
    common = sorted(
        [{"label": k, "count": v} for k, v in problem_counts.items()],
        key=lambda x: (-x["count"], x["label"]),
    )[:5]

    base_stats = {
        "affected_count": total,
        "signal_count": total,
        "account_signal_count": account_n,
        "feed_signal_count": feed_n,
        "unique_offer_count": len(all_offers),
        "feed_offer_count": len(feed_offers),
        "account_offer_count": len(account_offers),
        "account_share": round(account_share, 3),
        "feed_share": round(feed_share, 3),
        "common_problems": common,
        "disclaimer": (
            "Likely issue type from Merchant API signals — not Google’s official "
            "root-cause label or policy name."
        ),
    }

    # Thresholds (documented): dominate at ≥70%; both meaningful → MIXED
    if account_share >= 0.7 and feed_share < 0.2:
        issue_type = "ACCOUNT"
    elif feed_share >= 0.7 and account_share < 0.2:
        issue_type = "FEED"
    elif account_share >= 0.2 and feed_share >= 0.2:
        issue_type = "MIXED"
    elif account_share >= feed_share and account_n > 0:
        issue_type = "ACCOUNT"
    elif feed_n > 0:
        issue_type = "FEED"
    else:
        issue_type = "MIXED"

    if issue_type == "ACCOUNT":
        return {
            "issue_type": "ACCOUNT",
            "label": "Likely account-level issue",
            "headline": "Your account is the problem — not your feed.",
            "what_this_means": [
                "Google appears to be limiting your products because of an account-level policy issue.",
                "The exact policy name is shown in Merchant Center.",
            ],
            "what_you_should_do": [
                "Open Merchant Center",
                "Find the red policy warning",
                "Fix or appeal it there",
            ],
            "adfeed_can_help": False,
            "cta": "merchant_center",
            **base_stats,
        }

    if issue_type == "FEED":
        return {
            "issue_type": "FEED",
            "label": "Likely product / feed issue",
            "headline": "Your product feed is likely the problem.",
            "what_this_means": [
                "Your Merchant Center account does not appear to be the main issue.",
                "Most signals point to product-level data such as titles, brands, variants, or identifiers.",
            ],
            "what_you_should_do": [
                "Review the common feed issues in Evidence",
                "Fix the problematic feed fields in your catalog",
                "Generate a cleaner Shopping feed (AdFeed never invents GTINs)",
            ],
            "adfeed_can_help": True,
            "cta": "waitlist",
            **base_stats,
        }

    # MIXED
    return {
        "issue_type": "MIXED",
        "label": "Likely mixed: account + feed",
        "headline": "You may have two separate issues.",
        "what_this_means": [
            "This sample shows both account-level signals and product-data issues.",
            "Fix the account warning first — feed cleanup won’t help while the account is restricted.",
        ],
        "what_you_should_do": [
            "Fix the Merchant Center account policy warning first",
            "Then clean product/feed data",
            "Use AdFeed for the feed side after the account is clear",
        ],
        "adfeed_can_help": True,
        "cta": "both",
        **base_stats,
    }


# --- legacy helpers kept for enriching individual rows if needed elsewhere ---

def enrich_issue(code: str, reason_text: str = "") -> dict[str, str]:
    kind = bucket_for_code(code)
    google_text = (reason_text or "").strip()
    if kind == "account":
        return {
            "headline": "Likely account-level",
            "summary": google_text or "Account policy signal from Google.",
            "code_explain": "Account-level policy signal",
            "next_step": "Fix in Merchant Center.",
            "adfeed_help": "no",
            "adfeed_note": "AdFeed cannot clear account suspensions.",
            "google_reason": google_text,
        }
    label = feed_problem_label(code) or "Product data"
    return {
        "headline": label,
        "summary": google_text or f"Product/feed signal related to {label.lower()}.",
        "code_explain": label,
        "next_step": "Clean this field in the feed.",
        "adfeed_help": "yes",
        "adfeed_note": "AdFeed can help clean shopping feed fields.",
        "google_reason": google_text,
    }


def summarize_by_code(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for iss in issues:
        code = str(iss.get("reason_code") or "unknown")
        row = counts.setdefault(
            code,
            {"reason_code": code, "count": 0, **enrich_issue(code)},
        )
        row["count"] += 1
    return sorted(counts.values(), key=lambda r: (-r["count"], r["reason_code"]))


def build_diagnosis(issues: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Back-compat wrapper → prefer classify_issues()."""
    return classify_issues(issues)
