"""Workbench flags empty-image fatals so the UI can show a reason."""
from adfeed.feed_preview import _sku_sets_from_quality, build_workbench_product_rows


def test_i01_fatal_marks_need_image():
    qr = {
        "fatals": [
            {
                "level": "FATAL",
                "rule_id": "I01",
                "field": "g:image_link",
                "sku": "sku-empty-img",
                "message": "Main image is empty",
            }
        ],
        "warnings": [],
        "autofixed": [],
    }
    sets = _sku_sets_from_quality(qr)
    assert "sku-empty-img" in sets["fatal"]
    assert "sku-empty-img" in sets["image"]


def test_workbench_missing_status_sets_need_image_for_empty_feed_image(
    tmp_path, monkeypatch
):
    xml = """<?xml version="1.0"?>
<rss><channel>
<item>
  <g:id>sku-empty-img</g:id>
  <g:title>Minimal Board</g:title>
  <g:image_link></g:image_link>
</item>
</channel></rss>
"""
    path = tmp_path / "us.xml"
    path.write_text(xml, encoding="utf-8")
    qr = {
        "fatals": [
            {
                "rule_id": "I01",
                "field": "g:image_link",
                "sku": "sku-empty-img",
                "message": "Main image is empty",
            }
        ]
    }
    import adfeed.feed_preview as fp

    monkeypatch.setattr(
        fp,
        "resolve_product_feed_filter",
        lambda store_id, product_id: {
            "skus": {"sku-empty-img"},
            "group_prefixes": set(),
            "internal_id": "p1",
        },
    )
    rows = build_workbench_product_rows(
        store_id="s1",
        file_path=str(path),
        platform="google",
        products=[
            {
                "id": "p1",
                "title": "Minimal Board",
                "variant_skus": ["sku-empty-img"],
                "need_color": False,
                "need_size": False,
            }
        ],
        quality_report=qr,
    )
    assert len(rows) == 1
    assert rows[0]["feed_status"] == "missing"
    assert rows[0]["need_image"] is True
    assert rows[0]["fail_reason"] == "Main image is empty"
    assert rows[0]["needs_regenerate"] is False


def test_workbench_shopify_image_ready_asks_regenerate(tmp_path, monkeypatch):
    xml = """<?xml version="1.0"?>
<rss><channel>
<item>
  <g:id>sku-empty-img</g:id>
  <g:title>Minimal Board</g:title>
  <g:image_link></g:image_link>
</item>
</channel></rss>
"""
    path = tmp_path / "us.xml"
    path.write_text(xml, encoding="utf-8")
    qr = {
        "fatals": [
            {
                "rule_id": "I01",
                "field": "g:image_link",
                "sku": "sku-empty-img",
                "message": "Main image is empty",
            }
        ],
        "warnings": [
            {
                "rule_id": "M02",
                "field": "g:material",
                "sku": "sku-empty-img",
                "message": "Apparel missing material — GMC may flag incomplete attributes",
            }
        ],
    }
    import adfeed.feed_preview as fp

    monkeypatch.setattr(
        fp,
        "resolve_product_feed_filter",
        lambda store_id, product_id: {
            "skus": {"sku-empty-img"},
            "group_prefixes": set(),
            "internal_id": "p1",
        },
    )
    rows = build_workbench_product_rows(
        store_id="s1",
        file_path=str(path),
        platform="google",
        products=[
            {
                "id": "p1",
                "title": "Minimal Board",
                "image_url": "https://cdn.example.com/board.png",
                "variant_skus": ["sku-empty-img"],
                "need_color": False,
                "need_size": False,
            }
        ],
        quality_report=qr,
    )
    assert rows[0]["needs_regenerate"] is True
    assert rows[0]["need_image"] is False
    assert rows[0]["feed_status"] == "pending"
    assert rows[0]["fail_reason"] == (
        "Store image is up to date — click Generate again to refresh the feed"
    )
    assert "material" not in rows[0]["fail_reason"].lower()
    assert "empty" not in rows[0]["fail_reason"].lower()


def test_warn_only_not_needs_attention_but_has_warn_reason(tmp_path, monkeypatch):
    xml = """<?xml version="1.0"?>
<rss><channel>
<item>
  <g:id>gift-1</g:id>
  <g:title>Gift Card</g:title>
  <g:image_link>https://cdn.example.com/gift.png</g:image_link>
  <g:color>Assorted</g:color>
  <g:size>100</g:size>
</item>
</channel></rss>
"""
    path = tmp_path / "us.xml"
    path.write_text(xml, encoding="utf-8")
    qr = {
        "warnings": [
            {
                "rule_id": "M02",
                "field": "g:material",
                "sku": "gift-1",
                "message": "Apparel missing material — GMC may flag incomplete attributes",
            }
        ],
        "fatals": [],
        "autofixed": [],
    }
    import adfeed.feed_preview as fp

    monkeypatch.setattr(
        fp,
        "resolve_product_feed_filter",
        lambda store_id, product_id: {
            "skus": {"gift-1"},
            "group_prefixes": set(),
            "internal_id": "gift",
        },
    )
    rows = build_workbench_product_rows(
        store_id="s1",
        file_path=str(path),
        platform="google",
        products=[
            {
                "id": "gift",
                "title": "Gift Card",
                "image_url": "https://cdn.example.com/gift.png",
                "variant_skus": ["gift-1"],
                "need_color": False,
                "need_size": False,
            }
        ],
        quality_report=qr,
    )
    assert rows[0]["feed_status"] == "warn"
    assert rows[0]["needs_attention"] is False
    assert rows[0]["need_color"] is False
    assert rows[0]["need_size"] is False
    assert rows[0]["need_image"] is False
    assert "material" in rows[0]["warn_reason"].lower()
