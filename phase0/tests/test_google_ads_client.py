"""Parse Google Ads search rows into product metrics (no live network)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_metrics_from_ads_rows():
    from adfeed.google_ads_client import metrics_from_search_rows

    rows = [
        {
            "segments": {"date": "2026-08-29", "productItemId": "SKU-1"},
            "metrics": {
                "impressions": "10",
                "clicks": "2",
                "costMicros": "1500",
                "conversions": 0.5,
            },
        },
        {
            "campaign": {"id": "99"},
            "segments": {"date": "2026-08-29"},
            "metrics": {
                "impressions": "5",
                "clicks": "1",
                "costMicros": "500",
                "conversions": 0,
            },
        },
    ]
    out = metrics_from_search_rows(rows)
    assert out[0]["offer_id"] == "SKU-1"
    assert out[0]["cost_micros"] == 1500
    assert out[1].get("offer_id") in (None, "")
    assert out[1]["campaign_id"] == "99"


def test_http_ads_client_calls_search():
    from adfeed.google_ads_client import HttpAdsMetricsClient

    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "results": [
            {
                "segments": {"date": "2026-08-29", "productItemId": "SKU-1"},
                "metrics": {
                    "impressions": "1",
                    "clicks": "0",
                    "costMicros": "100",
                    "conversions": 0,
                },
            }
        ]
    }
    with patch("adfeed.platforms.google.ads_client.httpx.Client") as Client:
        inst = Client.return_value.__enter__.return_value
        inst.post.return_value = resp
        client = HttpAdsMetricsClient(
            access_token="tok",
            developer_token="dev",
        )
        rows = client.list_product_metrics("1234567890")
    assert rows[0]["offer_id"] == "SKU-1"
    assert "googleAds:search" in inst.post.call_args[0][0]
