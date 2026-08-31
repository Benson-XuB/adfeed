"""Mockable Google productInputs push client + run recording."""
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def store_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]
    from adfeed.db import init_db, create_user
    from adfeed import store_db

    init_db()
    store_db.init_store_schema()
    user = create_user(email=f"p-{uuid.uuid4().hex[:8]}@ex.com", name="P")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:8]}.myshopify.com",
        shop_name="Push Store",
    )
    return store_db, store


class Fake:
    def __init__(self):
        self.calls = []

    def insert_product_input(self, *, merchant_id, data_source, product_input):
        from adfeed.platforms.google.product_push import PushItemError

        self.calls.append(product_input["offerId"])
        if product_input["offerId"] == "BAD":
            raise PushItemError("INVALID", "no")
        return {"name": "accounts/1/productInputs/x"}


def _row(sku: str, **overrides):
    row = {
        "SKU": sku,
        "优化后标题": f"Title {sku}",
        "描述": "Desc",
        "颜色": "White",
        "价格": 10.0,
        "图片链接": "https://example.com/a.jpg",
        "链接": "https://example.com/p",
        "品牌": "Northline",
        "尺码": "M",
        "库存": 5,
        "_feed_currency": "USD",
        "identifier_exists": "no",
    }
    row.update(overrides)
    return row


def test_push_records_ok_and_fail(store_env):
    store_db, store = store_env
    from adfeed.platforms.google.product_push import push_canonical_rows

    store_db.upsert_google_merchant_account(store.id, "12345", "MC", select=True)
    ds = "accounts/12345/dataSources/api-primary"
    rows = [_row("OK-1"), _row("BAD")]
    client = Fake()
    run = push_canonical_rows(
        store.id,
        "12345",
        ds,
        rows,
        client=client,
    )
    assert run["ok_count"] == 1
    assert run["fail_count"] == 1
    assert run["id"]
    assert client.calls == ["OK-1", "BAD"]

    items = store_db.list_push_items(run["id"])
    by_offer = {i["offer_id"]: i for i in items}
    assert by_offer["OK-1"]["status"] == "ok"
    assert by_offer["BAD"]["status"] == "fail"
    assert by_offer["BAD"]["error_code"] == "INVALID"


def test_push_skips_rows_without_sku(store_env):
    store_db, store = store_env
    from adfeed.platforms.google.product_push import push_canonical_rows

    store_db.upsert_google_merchant_account(store.id, "99", "MC", select=True)
    ds = "accounts/99/dataSources/x"
    client = Fake()
    run = push_canonical_rows(
        store.id,
        "99",
        ds,
        [_row(""), _row("  "), _row("KEEP")],
        client=client,
    )
    assert client.calls == ["KEEP"]
    assert run["ok_count"] == 1
    assert run["fail_count"] == 0


def test_live_client_posts_insert_url():
    from adfeed.platforms.google.product_push import LiveProductPushClient, PushItemError

    client = LiveProductPushClient(access_token="tok-abc")
    product_input = {
        "offerId": "SKU-1",
        "contentLanguage": "en",
        "feedLabel": "US",
        "productAttributes": {"title": "Tee", "availability": "IN_STOCK"},
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"name": "accounts/1/productInputs/abc"}

    with patch("adfeed.platforms.google.product_push.httpx.Client") as ClientCls:
        ctx = ClientCls.return_value.__enter__.return_value
        ctx.post.return_value = mock_resp
        out = client.insert_product_input(
            merchant_id="12345",
            data_source="accounts/12345/dataSources/ds1",
            product_input=product_input,
        )

    assert out["name"] == "accounts/1/productInputs/abc"
    args, kwargs = ctx.post.call_args
    assert (
        args[0]
        == "https://merchantapi.googleapis.com/products/v1/accounts/12345/productInputs:insert"
    )
    assert kwargs["params"]["dataSource"] == "accounts/12345/dataSources/ds1"
    assert kwargs["headers"]["Authorization"] == "Bearer tok-abc"
    assert kwargs["json"]["offerId"] == "SKU-1"
    assert "productAttributes" in kwargs["json"]


def test_live_client_raises_push_item_error_on_http_fail():
    from adfeed.platforms.google.product_push import LiveProductPushClient, PushItemError

    client = LiveProductPushClient(access_token="tok")
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = '{"error":{"status":"INVALID_ARGUMENT","message":"bad"}}'
    mock_resp.json.return_value = {
        "error": {"status": "INVALID_ARGUMENT", "message": "bad"}
    }

    with patch("adfeed.platforms.google.product_push.httpx.Client") as ClientCls:
        ctx = ClientCls.return_value.__enter__.return_value
        ctx.post.return_value = mock_resp
        with pytest.raises(PushItemError) as ei:
            client.insert_product_input(
                merchant_id="1",
                data_source="accounts/1/dataSources/x",
                product_input={"offerId": "X"},
            )
    assert ei.value.code == "INVALID_ARGUMENT"
    assert "bad" in ei.value.message
