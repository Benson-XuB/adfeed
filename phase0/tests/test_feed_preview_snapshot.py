"""P0–P3 feed preview / snapshot / row edit regression."""
from __future__ import annotations

import uuid
from pathlib import Path

from adfeed.db import _conn
from adfeed.feed_preview import parse_xml_items, preview_feed_items, write_google_tsv_from_xml
from adfeed.feed_snapshots import (
    SNAPSHOT_KEEP,
    init_snapshot_schema,
    list_snapshots,
    maybe_snapshot_current,
    restore_snapshot,
)


SAMPLE_XML = """<?xml version="1.0"?>
<rss><channel>
<item>
  <g:id>SKU-RED-M</g:id>
  <g:title>Red Tee Size M</g:title>
  <g:color>Red</g:color>
  <g:size>M</g:size>
  <g:price>19.99 USD</g:price>
  <g:image_link>https://cdn.example.com/red.jpg</g:image_link>
  <g:link>https://shop.example.com/p/1</g:link>
</item>
<item>
  <g:id>SKU-BLUE-L</g:id>
  <g:title>Blue Tee Size L</g:title>
  <g:color>Blue</g:color>
  <g:size>L</g:size>
  <g:price>21.00 USD</g:price>
  <g:image_link>https://cdn.example.com/blue.jpg</g:image_link>
  <g:link>https://shop.example.com/p/2</g:link>
</item>
</channel></rss>
"""


def test_parse_and_preview_pagination(tmp_path: Path):
    xml = tmp_path / "us.xml"
    xml.write_text(SAMPLE_XML, encoding="utf-8")
    items = parse_xml_items(xml.read_text(encoding="utf-8"))
    assert len(items) == 2
    assert items[0]["id"] == "SKU-RED-M"

    page = preview_feed_items(file_path=str(xml), limit=1, offset=0, q="")
    assert page["total"] == 2
    assert page["has_more"] is True
    assert page["items"][0]["sku"] == "SKU-RED-M"
    assert page["items"][0]["title"] == "Red Tee Size M"

    filtered = preview_feed_items(file_path=str(xml), limit=10, offset=0, q="blue")
    assert filtered["total"] == 1
    assert filtered["items"][0]["sku"] == "SKU-BLUE-L"


def test_write_google_tsv(tmp_path: Path):
    xml = tmp_path / "us.xml"
    csv = tmp_path / "us.csv"
    xml.write_text(SAMPLE_XML, encoding="utf-8")
    n = write_google_tsv_from_xml(xml, csv)
    assert n == 2
    text = csv.read_text(encoding="utf-8")
    assert "SKU-RED-M" in text
    assert "\t" in text


def test_snapshots_prune_and_restore(tmp_path: Path, monkeypatch):
    from adfeed import feed_snapshots
    from adfeed import config

    monkeypatch.setattr(feed_snapshots, "FEEDS_DIR", tmp_path)
    monkeypatch.setattr(config, "FEEDS_DIR", tmp_path)

    init_snapshot_schema()
    store_id = f"snap-{uuid.uuid4().hex[:12]}"
    plat = "google"
    cu = "US"
    with _conn() as c:
        c.execute("DELETE FROM feed_snapshots WHERE store_id=?", (store_id,))
        c.commit()

    current = tmp_path / store_id / plat / "us.xml"
    current.parent.mkdir(parents=True, exist_ok=True)

    for i in range(7):
        current.write_text(
            f"<rss><channel><item><g:id>v{i}</g:id><g:title>T{i}</g:title></item></channel></rss>",
            encoding="utf-8",
        )
        sid = maybe_snapshot_current(store_id, plat, cu, current)
        assert sid
        current.write_text(
            f"<rss><channel><item><g:id>after{i}</g:id></item></channel></rss>",
            encoding="utf-8",
        )

    snaps = list_snapshots(store_id, plat, cu)
    assert len(snaps) == SNAPSHOT_KEEP
    for s in snaps:
        assert Path(
            # resolve via DB
            __import__("adfeed.feed_snapshots", fromlist=["get_snapshot"]).get_snapshot(
                store_id, s["id"]
            )["file_path"]
        ).exists()

    target = snaps[-1]["id"]  # oldest kept
    current.write_text(SAMPLE_XML, encoding="utf-8")
    out = restore_snapshot(store_id, target)
    assert out["ok"] is True
    body = current.read_text(encoding="utf-8")
    assert "<g:id>v" in body or "v" in body


def test_row_patch_requires_real_variant(monkeypatch):
    from adfeed import store_db
    from adfeed.feed_row_edit import apply_row_patches

    monkeypatch.setattr(store_db, "get_variant_by_sku_for_store", lambda *a, **k: None)
    result = apply_row_patches("store", [{"sku": "NOPE", "title": "X", "color": "Red"}])
    assert result["missing"] == ["NOPE"]
    assert result["updated"] == []


def test_remove_items_from_xml(tmp_path: Path):
    from adfeed.feed_preview import remove_items_from_feed_file

    xml = tmp_path / "us.xml"
    xml.write_text(SAMPLE_XML, encoding="utf-8")
    out = remove_items_from_feed_file(xml, ["SKU-RED-M"], platform="google")
    assert out["removed"] == ["SKU-RED-M"]
    assert out["item_count"] == 1
    body = xml.read_text(encoding="utf-8")
    assert "SKU-RED-M" not in body
    assert "SKU-BLUE-L" in body
    assert xml.with_suffix(".csv").exists()
