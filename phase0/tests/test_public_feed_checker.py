"""Public marketing Feed Checker — diagnose XML without inventing GTINs."""

from adfeed.public_tools.feed_checker import analyze_feed_bytes


def test_feed_checker_flags_missing_brand_and_long_title():
    xml = b"""<?xml version="1.0"?>
    <rss xmlns:g="http://base.google.com/ns/1.0" version="2.0">
      <channel>
        <item>
          <g:id>1</g:id>
          <title>Supplier Factory Brand Style Color Red Size XL Material Cotton Soft Soft Soft Soft Dress For Women New Arrival Hot Sale</title>
          <g:image_link>https://example.com/a.jpg</g:image_link>
        </item>
      </channel>
    </rss>"""
    report = analyze_feed_bytes(xml, max_items=10)
    assert report["item_count"] == 1
    codes = {b["code"] for b in report["buckets"]}
    assert "missing_brand" in codes
    assert "noisy_or_long_title" in codes
    # Must not recommend creating barcodes
    for b in report["buckets"]:
        advice = (b.get("advice") or "").lower()
        assert "create fake" in advice or "fake" not in advice or "do not create fake" in advice or "without fake" in advice
        assert "you should fake" not in advice
        assert "generate a gtin" not in advice
        assert "make up" not in advice


def test_feed_checker_flags_missing_image_and_identifier_advice():
    xml = b"""<?xml version="1.0"?>
    <rss xmlns:g="http://base.google.com/ns/1.0" version="2.0">
      <channel>
        <item>
          <g:id>2</g:id>
          <g:title>Clean Tee, Black, Size M</g:title>
          <g:brand>Acme</g:brand>
          <g:color>Black</g:color>
          <g:size>M</g:size>
        </item>
      </channel>
    </rss>"""
    report = analyze_feed_bytes(xml, max_items=10)
    codes = {b["code"] for b in report["buckets"]}
    assert "missing_image" in codes
    assert "missing_identifier" in codes
    advice = next(b["advice"] for b in report["buckets"] if b["code"] == "missing_identifier")
    assert "identifier_exists=no" in advice.lower() or "compliant" in advice.lower()
    assert "do not create fake" in advice.lower()
    assert "make up" not in advice.lower()


def test_feed_checker_respects_max_items():
    items = "".join(
        f"<item><g:id>{i}</g:id><g:title>Item {i}</g:title>"
        f"<g:brand>B</g:brand><g:image_link>https://x/{i}.jpg</g:image_link></item>"
        for i in range(8)
    )
    xml = f'<?xml version="1.0"?><rss xmlns:g="http://base.google.com/ns/1.0"><channel>{items}</channel></rss>'.encode()
    report = analyze_feed_bytes(xml, max_items=3)
    assert report["item_count"] == 3
    assert report["truncated"] is True
