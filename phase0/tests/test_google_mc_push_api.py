"""Unit tests for MC push load/push helpers."""
from pathlib import Path

from adfeed.google_mc_push.datasources import find_adfeed_api_source
from adfeed.google_mc_push.push import load_pushable_rows, push_rows


def test_find_adfeed_api_source_skips_file_input():
    sources = [
        {
            "name": "accounts/1/dataSources/9",
            "displayName": "AdFeed",
            "fileInput": {"fileName": "x.xml"},
        },
        {
            "name": "accounts/1/dataSources/42",
            "displayName": "AdFeed",
            "primaryProductDataSource": {"channel": "ONLINE_PRODUCTS"},
        },
    ]
    found = find_adfeed_api_source(sources)
    assert found["data_source_id"] == "42"


def test_load_pushable_rows_skips_excluded(tmp_path: Path):
    xml = """<?xml version="1.0"?><rss><channel>
      <item><g:id>A</g:id><g:title>One</g:title><g:link>https://x/a</g:link>
        <g:image_link>https://cdn/a.jpg</g:image_link><g:price>10.00 USD</g:price>
        <g:availability>in_stock</g:availability><g:brand>Acme</g:brand>
        <g:identifier_exists>no</g:identifier_exists></item>
      <item><g:id>B</g:id><g:title>Two</g:title><g:link>https://x/b</g:link>
        <g:image_link>https://cdn/b.jpg</g:image_link><g:price>11.00 USD</g:price>
        <g:availability>in_stock</g:availability><g:brand>Acme</g:brand>
        <g:identifier_exists>no</g:identifier_exists></item>
    </channel></rss>"""
    # feed_preview looks for <title> not <g:title> for plain — g:title becomes key title via g:(\w+)
    path = tmp_path / "f.xml"
    path.write_text(xml, encoding="utf-8")
    rows = load_pushable_rows(path, excluded_skus={"B"})
    assert [r["sku"] for r in rows] == ["A"]


def test_push_rows_partial_failure():
    rows = [
        {"sku": "OK", "title": "T", "链接": "https://x", "image_link": "https://i", "price": "1 USD", "brand": "B", "identifier_exists": "no", "gtin": ""},
        {"sku": "BAD", "title": "T", "链接": "https://x", "image_link": "https://i", "price": "1 USD", "brand": "B", "identifier_exists": "no", "gtin": ""},
    ]

    def _insert(_access, _mid, _ds, body):
        if body["offerId"] == "BAD":
            raise RuntimeError("boom")
        return {"name": "ok"}

    result = push_rows("tok", "123", "9", rows, insert_fn=_insert)
    assert result["success_count"] == 1
    assert result["failure_count"] == 1
    assert result["failures"][0]["offer_id"] == "BAD"
