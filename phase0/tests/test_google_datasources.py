"""Google API dataSources: list (API primary/supplemental) + select."""
import json
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SHOP = "datasources.myshopify.com"
MERCHANT_ID = "123"
API_DS_NAME = "accounts/123/dataSources/456"


@pytest.fixture()
def client_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("ADFEED_PUBLIC_URL", "https://example.test")
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]
    import adfeed.config as cfg

    cfg.SHOPIFY_CLIENT_ID = "test-client-id"
    cfg.SHOPIFY_CLIENT_SECRET = "test-client-secret"
    cfg.PUBLIC_BASE_URL = "https://example.test"
    cfg.WEB_SAAS_ENABLED = False

    from adfeed.db import init_db, create_user
    from adfeed import store_db
    from adfeed.api import app

    init_db()
    store_db.init_store_schema()
    user = create_user(email=f"ds-{uuid.uuid4().hex[:8]}@ex.com", name="DS")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=SHOP,
        shop_name="DataSources",
    )
    return TestClient(app), store_db, store


def _token(shop=SHOP):
    now = int(time.time())
    return jwt.encode(
        {
            "iss": f"https://{shop}/admin",
            "dest": f"https://{shop}",
            "aud": "test-client-id",
            "sub": "1",
            "exp": now + 120,
            "nbf": now - 5,
            "iat": now,
            "jti": str(uuid.uuid4()),
        },
        "test-client-secret",
        algorithm="HS256",
    )


def _auth_headers():
    return {"Authorization": f"Bearer {_token()}"}


def _connect_google(store_db, store):
    store_db.upsert_google_oauth_token(
        store.id,
        "enc-refresh",
        "https://www.googleapis.com/auth/content",
    )
    store_db.upsert_google_merchant_account(
        store.id, MERCHANT_ID, "MC Test", select=True
    )


# --- unit: filter + list_api_data_sources ---


def test_filter_keeps_api_primary_and_supplemental_only():
    from adfeed.platforms.google.datasources import filter_api_product_data_sources

    raw = [
        {
            "name": API_DS_NAME,
            "displayName": "API Primary",
            "input": "API",
            "primaryProductDataSource": {"feedLabel": "US", "contentLanguage": "en"},
        },
        {
            "name": "accounts/123/dataSources/789",
            "displayName": "API Supplemental",
            "input": "API",
            "supplementalProductDataSource": {},
        },
        {
            "name": "accounts/123/dataSources/ui",
            "displayName": "UI Primary",
            "input": "UI",
            "primaryProductDataSource": {"feedLabel": "US"},
        },
        {
            "name": "accounts/123/dataSources/promo",
            "displayName": "API Promo",
            "input": "API",
            "promotionDataSource": {"targetCountry": "US", "contentLanguage": "en"},
        },
        {
            "name": "accounts/123/dataSources/file",
            "displayName": "File",
            "input": "FILE",
            "primaryProductDataSource": {"feedLabel": "CA"},
        },
    ]
    out = filter_api_product_data_sources(raw)
    names = {d["name"] for d in out}
    assert names == {API_DS_NAME, "accounts/123/dataSources/789"}


def test_list_api_data_sources_uses_mockable_client():
    from adfeed.platforms.google.datasources import list_api_data_sources

    class Fake:
        def list_data_sources(self, merchant_id: str):
            assert merchant_id == MERCHANT_ID
            return [
                {
                    "name": API_DS_NAME,
                    "input": "API",
                    "primaryProductDataSource": {},
                },
                {
                    "name": "accounts/123/dataSources/ui",
                    "input": "UI",
                    "primaryProductDataSource": {},
                },
            ]

    out = list_api_data_sources(MERCHANT_ID, "tok", client=Fake())
    assert len(out) == 1
    assert out[0]["name"] == API_DS_NAME


def test_http_client_list_data_sources_paginates():
    from adfeed.platforms.google.datasources import HttpDataSourcesClient

    page1 = {
        "dataSources": [
            {
                "name": API_DS_NAME,
                "input": "API",
                "primaryProductDataSource": {},
            }
        ],
        "nextPageToken": "p2",
    }
    page2 = {
        "dataSources": [
            {
                "name": "accounts/123/dataSources/789",
                "input": "API",
                "supplementalProductDataSource": {},
            }
        ],
    }
    resp1 = MagicMock(status_code=200)
    resp1.json.return_value = page1
    resp2 = MagicMock(status_code=200)
    resp2.json.return_value = page2

    with patch("adfeed.platforms.google.datasources.httpx.Client") as Client:
        inst = Client.return_value.__enter__.return_value
        inst.get.side_effect = [resp1, resp2]
        client = HttpDataSourcesClient(access_token="tok")
        items = client.list_data_sources(MERCHANT_ID)
    assert len(items) == 2
    assert inst.get.call_count == 2
    assert "accounts/123/dataSources" in inst.get.call_args_list[0].args[0]


def test_ensure_api_primary_returns_existing_without_create():
    from adfeed.platforms.google.datasources import ensure_api_primary_data_source

    class Fake:
        created = False

        def list_data_sources(self, merchant_id: str):
            return [
                {
                    "name": API_DS_NAME,
                    "input": "API",
                    "primaryProductDataSource": {"feedLabel": "US"},
                }
            ]

        def create_primary_api_data_source(self, merchant_id: str, **kwargs):
            self.created = True
            raise AssertionError("should not create")

    out = ensure_api_primary_data_source(MERCHANT_ID, "tok", client=Fake())
    assert out["name"] == API_DS_NAME


def test_ensure_api_primary_creates_when_none(monkeypatch):
    from adfeed.platforms.google.datasources import ensure_api_primary_data_source

    class Fake:
        def list_data_sources(self, merchant_id: str):
            return []

        def create_primary_api_data_source(self, merchant_id: str, **kwargs):
            return {
                "name": "accounts/123/dataSources/new",
                "input": "API",
                "primaryProductDataSource": {},
            }

    out = ensure_api_primary_data_source(MERCHANT_ID, "tok", client=Fake())
    assert out["name"] == "accounts/123/dataSources/new"


# --- router ---


def test_list_datasources_requires_oauth(client_env):
    client, store_db, store = client_env
    store_db.upsert_google_merchant_account(
        store.id, MERCHANT_ID, "MC", select=True
    )
    res = client.get(
        "/api/app/google/datasources",
        headers=_auth_headers(),
    )
    assert res.status_code == 400
    assert "Connect Google" in res.json()["detail"]


def test_list_datasources_mock_result_query(client_env):
    client, store_db, store = client_env
    _connect_google(store_db, store)
    res = client.get(
        "/api/app/google/datasources",
        headers=_auth_headers(),
        params={"mock_result": "1"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["merchant_id"] == MERCHANT_ID
    names = [d["name"] for d in body["data_sources"]]
    assert API_DS_NAME in names


def test_list_datasources_mock_result_body_via_post_select_path_not_required(client_env):
    """GET also accepts mock_result as JSON list string in query for CI."""
    client, store_db, store = client_env
    _connect_google(store_db, store)
    fake = [{"name": API_DS_NAME, "input": "API", "displayName": "Fake"}]
    res = client.get(
        "/api/app/google/datasources",
        headers=_auth_headers(),
        params={"mock_result": json.dumps(fake)},
    )
    assert res.status_code == 200, res.text
    assert res.json()["data_sources"][0]["name"] == API_DS_NAME


def test_select_datasource_persists(client_env):
    client, store_db, store = client_env
    _connect_google(store_db, store)
    res = client.post(
        "/api/app/google/datasources/select",
        headers=_auth_headers(),
        json={
            "data_source_name": API_DS_NAME,
            "mock_result": [{"name": API_DS_NAME, "input": "API"}],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["merchant"]["data_source_name"] == API_DS_NAME
    merchants = store_db.list_google_merchant_accounts(store.id)
    selected = next(m for m in merchants if m["merchant_id"] == MERCHANT_ID)
    assert selected["data_source_name"] == API_DS_NAME


def test_select_rejects_name_not_in_api_list(client_env):
    client, store_db, store = client_env
    _connect_google(store_db, store)
    res = client.post(
        "/api/app/google/datasources/select",
        headers=_auth_headers(),
        json={
            "data_source_name": "accounts/123/dataSources/ui-not-api",
            "mock_result": [{"name": API_DS_NAME, "input": "API"}],
        },
    )
    assert res.status_code == 400
    assert "dataSource" in res.json()["detail"] or "not" in res.json()["detail"].lower()
    merchants = store_db.list_google_merchant_accounts(store.id)
    selected = next(m for m in merchants if m["merchant_id"] == MERCHANT_ID)
    assert not (selected.get("data_source_name") or "").strip()


def test_select_datasource_requires_oauth(client_env):
    client, store_db, store = client_env
    store_db.upsert_google_merchant_account(
        store.id, MERCHANT_ID, "MC", select=True
    )
    res = client.post(
        "/api/app/google/datasources/select",
        headers=_auth_headers(),
        json={
            "data_source_name": API_DS_NAME,
            "mock_result": [{"name": API_DS_NAME}],
        },
    )
    assert res.status_code == 400
    assert "Connect Google" in res.json()["detail"]


def test_select_works_without_push_flag(client_env, monkeypatch):
    client, store_db, store = client_env
    monkeypatch.delenv("GOOGLE_PUSH_ENABLED", raising=False)
    _connect_google(store_db, store)
    res = client.post(
        "/api/app/google/datasources/select",
        headers=_auth_headers(),
        json={
            "data_source_name": API_DS_NAME,
            "merchant_id": MERCHANT_ID,
            "mock_result": 1,
        },
    )
    assert res.status_code == 200, res.text
