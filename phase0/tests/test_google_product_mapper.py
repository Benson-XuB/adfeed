"""Map canonical Chinese-key feed rows → Merchant ProductInput."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _base_row(**overrides):
    row = {
        "SKU": "NL-TEE-WHT-M",
        "优化后标题": "Tee",
        "描述": "Soft cotton tee",
        "颜色": "White",
        "价格": 18.0,
        "图片链接": "https://example.com/tee.jpg",
        "链接": "https://example.com/products/nl-tee-wht-m",
        "品牌": "Northline",
        "gender": "unisex",
        "age_group": "adult",
        "材质": "Cotton",
        "尺码": "M",
        "GPC代码": "212",
        "item_group_id": "NL-TEE",
        "pattern": "",
        "shipping_weight": "0.2 kg",
        "库存": 10,
        "_feed_currency": "USD",
        "identifier_exists": "no",
        "gtin": "",
    }
    row.update(overrides)
    return row


def test_mapper_offer_id_is_sku_and_skips_fake_gtin():
    from adfeed.platforms.google.product_mapper import map_row_to_product_input

    row = _base_row()
    body = map_row_to_product_input(
        row, channel="online", content_language="en", feed_label="US"
    )
    assert body["offerId"] == "NL-TEE-WHT-M"
    assert body["contentLanguage"] == "en"
    assert body["feedLabel"] == "US"
    assert "gtin" not in body or not body.get("gtin")
    attrs = body["productAttributes"]
    assert "attributes" not in body
    assert attrs["color"] == "White"
    assert "gtin" not in attrs or not attrs.get("gtin")
    assert "gtins" not in attrs or not attrs.get("gtins")
    assert attrs["price"] == {"amountMicros": "18000000", "currencyCode": "USD"}
    assert attrs["title"] == "Tee"
    assert attrs["availability"] == "IN_STOCK"
    assert attrs["condition"] == "NEW"
    assert attrs["sizes"] == ["M"]
    assert attrs["brand"] == "Northline"
    assert attrs["itemGroupId"] == "NL-TEE"
    assert attrs["googleProductCategory"] == "212"
    assert attrs["shippingWeight"] == {"value": 0.2, "unit": "kg"}


def test_mapper_omits_empty_color_no_multicolor():
    from adfeed.platforms.google.product_mapper import map_row_to_product_input

    row = _base_row(颜色="", 优化后标题="Tee Multicolor Look")
    body = map_row_to_product_input(
        row, channel="online", content_language="en", feed_label="US"
    )
    attrs = body["productAttributes"]
    assert "color" not in attrs
    assert attrs.get("color") != "Multicolor"


def test_mapper_includes_gtin_only_when_real_and_identifier_exists():
    from adfeed.platforms.google.product_mapper import map_row_to_product_input

    # Real gtin but identifier_exists=no → omit
    row_no = _base_row(gtin="012345678905", identifier_exists="no")
    body_no = map_row_to_product_input(
        row_no, channel="online", content_language="en", feed_label="US"
    )
    attrs_no = body_no["productAttributes"]
    assert "gtin" not in attrs_no or not attrs_no.get("gtin")
    assert "gtins" not in attrs_no or not attrs_no.get("gtins")

    # Empty gtin with identifier_exists=yes → omit (never invent)
    row_empty = _base_row(gtin="", identifier_exists="yes")
    body_empty = map_row_to_product_input(
        row_empty, channel="online", content_language="en", feed_label="US"
    )
    attrs_empty = body_empty["productAttributes"]
    assert "gtin" not in attrs_empty or not attrs_empty.get("gtin")
    assert "gtins" not in attrs_empty or not attrs_empty.get("gtins")

    # Real gtin + identifier_exists=yes → include
    row_yes = _base_row(gtin="012345678905", identifier_exists="yes")
    body_yes = map_row_to_product_input(
        row_yes, channel="online", content_language="en", feed_label="US"
    )
    attrs_yes = body_yes["productAttributes"]
    assert attrs_yes.get("gtins") == ["012345678905"] or attrs_yes.get("gtin") == "012345678905"


def test_mapper_omits_empty_brand():
    from adfeed.platforms.google.product_mapper import map_row_to_product_input

    row = _base_row(品牌="")
    body = map_row_to_product_input(
        row, channel="online", content_language="en", feed_label="US"
    )
    attrs = body["productAttributes"]
    assert "brand" not in attrs


def test_mapper_out_of_stock_enum():
    from adfeed.platforms.google.product_mapper import map_row_to_product_input

    row = _base_row(库存=0)
    body = map_row_to_product_input(
        row, channel="online", content_language="en", feed_label="US"
    )
    assert body["productAttributes"]["availability"] == "OUT_OF_STOCK"
