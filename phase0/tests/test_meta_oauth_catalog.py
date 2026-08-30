import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _meta_env(monkeypatch):
    monkeypatch.setenv("META_APP_ID", "app")
    monkeypatch.setenv("META_APP_SECRET", "secret")
    monkeypatch.setenv("META_OAUTH_REDIRECT_URI", "https://example.com/meta/cb")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-meta")


def test_meta_state_roundtrip():
    from adfeed.platforms.meta.oauth import make_oauth_state, parse_oauth_state

    st = make_oauth_state("store-9")
    assert parse_oauth_state(st)["store_id"] == "store-9"


def test_meta_seal_token_roundtrip():
    from adfeed.platforms.meta.oauth import open_access_token, seal_access_token

    sealed = seal_access_token("tok-1")
    assert open_access_token(sealed) == "tok-1"


def test_catalogs_from_graph_payload():
    from adfeed.platforms.meta.catalog_client import catalogs_from_graph_payload

    rows = catalogs_from_graph_payload(
        {"data": [{"id": "111", "name": "Main"}, {"id": "222"}]}
    )
    assert rows[0]["catalog_id"] == "111"
    assert rows[0]["display_name"] == "Main"


def test_attach_scheduled_feed_posts(monkeypatch):
    from adfeed.platforms.meta.catalog_client import HttpMetaCatalogClient

    posts = []

    def fake_post(self, path, data):
        posts.append((path, data))
        if path.endswith("/product_feeds"):
            return {"id": "feed-9"}
        return {"id": "upload-1"}

    monkeypatch.setattr(HttpMetaCatalogClient, "_post", fake_post)
    client = HttpMetaCatalogClient("tok")
    out = client.attach_scheduled_feed(
        "cat-1", feed_url="https://deltfu.com/feeds/s/meta/us.xml"
    )
    assert out["product_feed_id"] == "feed-9"
    assert posts[0][0] == "/cat-1/product_feeds"
