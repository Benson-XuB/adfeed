"""Google Ads monitor public API — live when OAuth is configured."""

from adfeed.public_tools.google_ads_oauth import (
    google_ads_api_configured,
    google_ads_oauth_configured,
)
from adfeed.public_tools.google_ads_report import demo_report


def test_demo_report_has_rows_and_demo_mode():
    report = demo_report()
    assert report["mode"] == "demo"
    assert report["ok"] is True
    assert len(report["rows"]) >= 20
    assert report["rows"][0]["d"].startswith("2026-")
    assert "sample" in report["notice"].lower() or "Connect" in report["notice"]


def test_ads_api_configured_with_oauth_only(monkeypatch):
    """After developer-token sunset, Cloud project + OAuth is enough for live."""
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN", raising=False)
    assert google_ads_oauth_configured() is False
    assert google_ads_api_configured() is False

    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "x")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "y")
    assert google_ads_oauth_configured() is True
    assert google_ads_api_configured() is True
