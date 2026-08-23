"""Image risk classification (feed picker uses this; AI watermark path removed from product)."""
from adfeed.image_processor import classify_image_risk


def test_alicdn_flagged_risky():
    assert classify_image_risk("https://cbu01.alicdn.com/img/foo.jpg")["risky"] is True


def test_shopify_cdn_not_auto_risky():
    assert classify_image_risk("https://cdn.shopify.com/s/files/1/x/a.jpg")["risky"] is False


def test_1688_flagged_risky():
    assert classify_image_risk("https://img.1688.com/bao/foo.jpg")["risky"] is True
