"""Pipeline helpers: preflight + link pin wiring (no Shopify DB)."""
from adfeed.feed_link import build_product_link
from adfeed.market_pricing import PreflightStatus, preflight_country, resolve_market_price


def test_cny_shop_us_target_blocked():
    pf = preflight_country("CNY", "US")
    assert pf.status == PreflightStatus.RED


def test_usd_shop_us_link_pinned():
    priced = resolve_market_price(29.99, "USD", "US")
    assert priced.ok
    link = build_product_link(
        "https://qx2kd5-s7.myshopify.com/products/dress",
        variant_id="111",
        currency=priced.currency,
    )
    assert "currency=USD" in link
    assert "variant=111" in link


def test_meta_feed_no_fx():
    from adfeed.multi_platform_feeds import generate_meta_feed

    rows = [{
        "SKU": "s1",
        "优化后标题": "Dress",
        "描述": "Desc",
        "链接": "https://shop.example.com/p?currency=USD",
        "图片链接": "https://cdn.example.com/a.jpg",
        "附加图片": "",
        "价格": 100.0,
        "_feed_currency": "USD",
        "库存": 2,
        "品牌": "eprolo",
        "GPC代码": "2271",
        "item_group_id": "g",
        "颜色": "Black",
        "尺码": "M",
        "材质": "Cotton",
        "gender": "female",
        "age_group": "adult",
    }]
    xml = generate_meta_feed(rows, shop_name="Test", site_link="https://x.com", country="DE")
    assert "<price>100.00 USD</price>" in xml
    assert "92.00 EUR" not in xml
