from adfeed.public_tools.google_issues import issues_from_report_rows
from adfeed.public_tools.issue_copy import classify_issues, enrich_issue


def test_enrich_account_policy_says_adfeed_cannot_clear():
    meta = enrich_issue("policy_enforcement_account_disapproval")
    assert meta["adfeed_help"] == "no"
    assert "account" in meta["headline"].lower()


def test_classify_account_dominant():
    rows = [
        {
            "productView": {
                "offerId": f"SKU-{i}",
                "title": "Dress",
                "itemIssues": [
                    {
                        "type": {"code": "policy_enforcement_account_disapproval"},
                        "severity": {"aggregatedSeverity": "DISAPPROVED"},
                    }
                ],
            }
        }
        for i in range(5)
    ]
    issues = issues_from_report_rows(rows)
    diag = classify_issues(issues)
    assert diag["issue_type"] == "ACCOUNT"
    assert diag["adfeed_can_help"] is False
    assert diag["cta"] == "merchant_center"
    assert "likely account" in diag["label"].lower()
    assert diag["headline"]
    assert isinstance(diag["what_this_means"], list)
    assert diag["account_signal_count"] == 5


def test_classify_feed_dominant():
    codes = ["title", "brand", "missing_item_attribute", "gtin", "image_link"]
    rows = []
    for i, code in enumerate(codes):
        rows.append(
            {
                "productView": {
                    "offerId": f"SKU-{i}",
                    "title": "Item",
                    "itemIssues": [{"type": {"code": code}}],
                }
            }
        )
    issues = issues_from_report_rows(rows)
    diag = classify_issues(issues)
    assert diag["issue_type"] == "FEED"
    assert diag["adfeed_can_help"] is True
    assert diag["cta"] == "waitlist"
    assert diag["common_problems"]
    assert diag["feed_offer_count"] == 5
    assert diag["headline"]


def test_classify_mixed():
    rows = []
    for i in range(3):
        rows.append(
            {
                "productView": {
                    "offerId": f"A-{i}",
                    "title": "A",
                    "itemIssues": [
                        {"type": {"code": "policy_enforcement_account_disapproval"}}
                    ],
                }
            }
        )
    for i in range(3):
        rows.append(
            {
                "productView": {
                    "offerId": f"F-{i}",
                    "title": "F",
                    "itemIssues": [{"type": {"code": "brand"}}],
                }
            }
        )
    issues = issues_from_report_rows(rows)
    diag = classify_issues(issues)
    assert diag["issue_type"] == "MIXED"
    assert diag["cta"] == "both"
    assert diag["account_signal_count"] == 3
    assert diag["feed_signal_count"] == 3


def test_demo_diagnosis_kinds():
    from adfeed.public_tools.google_issues import demo_diagnosis

    assert demo_diagnosis("account")["diagnosis"]["issue_type"] == "ACCOUNT"
    assert demo_diagnosis("feed")["diagnosis"]["issue_type"] == "FEED"
    assert demo_diagnosis("mixed")["diagnosis"]["issue_type"] == "MIXED"
    assert demo_diagnosis("none")["diagnosis"]["issue_type"] == "NONE"
    feed = demo_diagnosis("feed")["diagnosis"]
    assert feed["common_problems"]
    assert feed["feed_offer_count"] > 0

