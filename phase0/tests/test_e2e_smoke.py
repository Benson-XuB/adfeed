"""Plan Task 11 automated smoke (no live Shopify / LLM)."""
import json
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def client_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("ADFEED_PUBLIC_URL", "https://deltfu.com")
    monkeypatch.setenv("ADFEED_WEBHOOK_SKIP_HMAC", "true")
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]
    import adfeed.config as cfg
    cfg.SHOPIFY_CLIENT_ID = "test-client-id"
    cfg.SHOPIFY_CLIENT_SECRET = "test-client-secret"
    cfg.PUBLIC_BASE_URL = "https://deltfu.com"
    cfg.WEB_SAAS_ENABLED = False

    from adfeed.db import init_db, create_user
    init_db()
    from adfeed import store_db
    store_db.init_store_schema()
    from adfeed.api import app
    user = create_user(email=f"e2e-{uuid.uuid4().hex[:8]}@ex.com", name="E2E")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain="e2e.myshopify.com",
        quota_total=100,
    )
    pids = []
    for i in range(3):
        p = store_db.save_product(
            store.id, title=f"Product {i}", shopify_product_id=str(1000 + i),
        )
        pids.append(p.id)
    return TestClient(app), store_db, store, pids


def _token(shop="e2e.myshopify.com"):
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


def test_unauthenticated_generate_401(client_env):
    client, *_ = client_env
    res = client.post("/api/app/generate", json={
        "product_ids": ["1"],
        "platforms": ["google"],
        "languages": ["US"],
    })
    assert res.status_code == 401


def test_estimate_12_for_3x2x2(client_env):
    client, _, _, pids = client_env
    res = client.post(
        "/api/app/quota/estimate",
        headers={"Authorization": f"Bearer {_token()}"},
        json={
            "product_ids": pids,
            "platforms": ["google", "meta"],
            "languages": ["US", "DE"],
        },
    )
    assert res.status_code == 200
    assert res.json()["estimate"] == 12


def test_generate_writes_four_feeds_and_debits(client_env):
    client, store_db, store, pids = client_env
    token = _token()

    fake_multi = {
        "optimized_titles": {"US": "Title US", "DE": "Title DE"},
        "description_snippets": {"US": "D", "DE": "D"},
        "ai_tags_by_lang": {"US": [], "DE": []},
    }

    with patch("adfeed.pipeline.load_gpc_taxonomy"), \
         patch("adfeed.pipeline.gpc_match", return_value={
             "gpc_code": "2271", "gpc_path": "Apparel", "confidence": 1, "source": "t",
         }), \
         patch("adfeed.pipeline.optimize_multi_country", return_value=fake_multi), \
         patch("adfeed.pipeline.infer_product_attributes", return_value={}), \
         patch("adfeed.pipeline.generate_feed_xml", return_value="<rss><channel><item></item></channel></rss>"), \
         patch("adfeed.multi_platform_feeds.generate_meta_feed", return_value="<rss><channel><item></item></channel></rss>"):
        res = client.post(
            "/api/app/generate",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "product_ids": pids,
                "platforms": ["google", "meta"],
                "languages": ["US", "DE"],
                "remove_watermarks": False,
            },
        )
        assert res.status_code == 200
        job_id = res.json()["job_id"]
        assert res.json()["estimate"] == 12

        # Poll until done (background thread)
        deadline = time.time() + 30
        final = None
        while time.time() < deadline:
            st = client.get(
                f"/api/app/jobs/{job_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert st.status_code == 200
            final = st.json()
            if final["status"] in ("completed", "failed"):
                break
            time.sleep(0.2)

    assert final is not None
    assert final["status"] == "completed", final
    feeds = (final.get("result") or {}).get("feeds") or []
    assert len(feeds) == 4
    urls = {f["url"] for f in feeds}
    assert any("/google/us.xml" in u for u in urls)
    assert any("/meta/de.xml" in u for u in urls)

    refreshed = store_db.get_store(store.id)
    assert refreshed.quota_used == 12


def test_web_saas_upload_retired(client_env):
    client, *_ = client_env
    res = client.post("/api/auth/magic-link", json={"email": "a@b.com"})
    assert res.status_code == 410
