"""Parse Merchant reports.search rows into issue dicts (no live network)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_normalize_report_rows_to_issues():
    from adfeed.google_merchant_client import issues_from_report_rows

    rows = [
        {
            "productView": {
                "offerId": "SKU-1",
                "id": "en~US~SKU-1",
                "itemIssues": [
                    {
                        "type": {"code": "image_missing"},
                        "severity": {"aggregatedSeverity": "DISAPPROVED"},
                        "description": "Missing image",
                    }
                ],
            }
        },
        {
            "productView": {
                "offerId": "SKU-2",
                "itemIssues": [
                    {
                        "type": {"code": "missing_color"},
                        "severity": {"aggregatedSeverity": "DEMOTED"},
                        "description": "Color",
                    }
                ],
            }
        },
    ]
    issues = issues_from_report_rows(rows)
    assert len(issues) == 2
    by = {i["offer_id"]: i for i in issues}
    assert by["SKU-1"]["status"] == "disapproved"
    assert by["SKU-1"]["reason_code"] == "image_missing"
    assert by["SKU-2"]["status"] == "demoted"


def test_http_client_list_product_issues_paginates():
    from adfeed.google_merchant_client import HttpMerchantClient

    page1 = {
        "results": [
            {
                "productView": {
                    "offerId": "A",
                    "itemIssues": [
                        {
                            "type": {"code": "x"},
                            "severity": {"aggregatedSeverity": "DISAPPROVED"},
                            "description": "d",
                        }
                    ],
                }
            }
        ],
        "nextPageToken": "p2",
    }
    page2 = {
        "results": [
            {
                "productView": {
                    "offerId": "B",
                    "itemIssues": [
                        {
                            "type": {"code": "y"},
                            "severity": {"aggregatedSeverity": "DISAPPROVED"},
                            "description": "d2",
                        }
                    ],
                }
            }
        ],
    }
    resp1 = MagicMock(status_code=200)
    resp1.json.return_value = page1
    resp2 = MagicMock(status_code=200)
    resp2.json.return_value = page2

    with patch("adfeed.platforms.google.merchant_client.httpx.Client") as Client:
        inst = Client.return_value.__enter__.return_value
        inst.post.side_effect = [resp1, resp2]
        client = HttpMerchantClient(access_token="tok")
        issues = client.list_product_issues("12345")
    assert {i["offer_id"] for i in issues} == {"A", "B"}
    assert inst.post.call_count == 2


def test_authinfo_merchants_parsed():
    from adfeed.google_merchant_client import merchants_from_authinfo

    payload = {
        "accountIdentifiers": [
            {"merchantId": "111", "aggregatorId": "999"},
            {"merchantId": "222"},
        ]
    }
    ms = merchants_from_authinfo(payload)
    assert ms[0]["merchant_id"] == "111"
    assert ms[1]["merchant_id"] == "222"
