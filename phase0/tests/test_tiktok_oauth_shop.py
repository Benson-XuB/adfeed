import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _tt_env(monkeypatch):
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "key")
    monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "secret")
    monkeypatch.setenv("TIKTOK_OAUTH_REDIRECT_URI", "https://example.com/tt/cb")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-tiktok-secret-32b!!")


def test_tiktok_state_and_seal():
    from adfeed.platforms.tiktok.oauth import (
        make_oauth_state,
        open_token,
        parse_oauth_state,
        seal_token,
    )

    assert parse_oauth_state(make_oauth_state("s1"))["store_id"] == "s1"
    assert open_token(seal_token("abc")) == "abc"


def test_shops_from_payload():
    from adfeed.platforms.tiktok.shop_client import shops_from_payload

    rows = shops_from_payload(
        {"data": {"shops": [{"id": "9", "name": "Shop A", "cipher": "c1"}]}}
    )
    assert rows[0]["shop_id"] == "9"
    assert rows[0]["cipher"] == "c1"


def test_register_feed_url():
    from adfeed.platforms.tiktok.shop_client import HttpTikTokShopClient

    out = HttpTikTokShopClient("tok").register_feed_url(
        "shop-1", "https://deltfu.com/feeds/x/tiktok/us.csv"
    )
    assert out["mode"] == "register"
    assert out["feed_url"].endswith(".csv")


def test_sign_request_stable():
    from adfeed.platforms.tiktok.shop_client import sign_request

    s1 = sign_request("sec", path="/authorization/202309/shops", params={"a": "1", "b": "2"})
    s2 = sign_request("sec", path="/authorization/202309/shops", params={"b": "2", "a": "1"})
    assert s1 == s2
    assert len(s1) == 64
