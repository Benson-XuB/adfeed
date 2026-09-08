"""HTTP tests for public feed-check API."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def public_client(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]
    from adfeed.db import init_db

    init_db()
    from adfeed.api import app

    return TestClient(app)


def test_feed_check_upload_returns_buckets(public_client):
    xml = b"""<?xml version="1.0"?>
    <rss xmlns:g="http://base.google.com/ns/1.0"><channel>
      <item>
        <g:id>1</g:id>
        <title>Supplier Factory Soft Soft Soft Soft Soft Dress New Arrival Hot Sale XL</title>
        <g:image_link>https://example.com/a.jpg</g:image_link>
      </item>
    </channel></rss>"""
    res = public_client.post(
        "/api/public/feed-check/upload",
        files={"file": ("feed.xml", xml, "application/xml")},
        data={"max_items": "50"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["item_count"] == 1
    codes = {b["code"] for b in data["buckets"]}
    assert "missing_brand" in codes
    assert data["adfeed_helps"]
