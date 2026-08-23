"""Public privacy/support pages required for App Store listing URLs."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def legal_client(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "test-client-secret")
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]
    import adfeed.config as cfg
    cfg.SHOPIFY_CLIENT_SECRET = "test-client-secret"
    from adfeed.db import init_db
    init_db()
    from adfeed import store_db
    store_db.init_store_schema()
    from adfeed.api import app
    return TestClient(app)


def test_privacy_page_explains_shop_data_not_customer_pii(legal_client):
    res = legal_client.get("/api/privacy")
    assert res.status_code == 200
    body = res.text.lower()
    assert "privacy" in body
    assert "customer" in body
    assert "merchant center" not in body or "not guarantee" in body or "does not guarantee" in body
    assert "shop/redact" in body or "uninstall" in body


def test_support_page_has_contact(legal_client):
    res = legal_client.get("/api/support")
    assert res.status_code == 200
    body = res.text.lower()
    assert "support" in body
    assert "@" in res.text
