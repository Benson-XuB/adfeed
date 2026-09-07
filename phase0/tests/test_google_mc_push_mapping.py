from adfeed.google_mc_push.mapping import feed_row_to_product_input


def test_maps_offer_id_and_does_not_invent_gtin():
    row = {
        "sku": "SKU-1",
        "title": "Black Dress Size M",
        "链接": "https://shop.example.com/products/d?variant=1",
        "image_link": "https://cdn.example/a.jpg",
        "price": "19.99 USD",
        "availability": "in_stock",
        "condition": "new",
        "brand": "Acme",
        "color": "Black",
        "size": "M",
        "item_group_id": "111",
        "identifier_exists": "no",
        "gtin": "",
    }
    body = feed_row_to_product_input(row, content_language="en", feed_label="US")
    assert body["offerId"] == "SKU-1"
    assert body["contentLanguage"] == "en"
    assert body["feedLabel"] == "US"
    attrs = body["productAttributes"]
    assert attrs["title"] == "Black Dress Size M"
    assert attrs["brand"] == "Acme"
    assert attrs["link"] == "https://shop.example.com/products/d?variant=1"
    assert attrs["imageLink"] == "https://cdn.example/a.jpg"
    assert attrs["price"]["amountMicros"] == "19990000"
    assert attrs["price"]["currencyCode"] == "USD"
    assert attrs["availability"] == "IN_STOCK"
    assert attrs["identifierExists"] is False
    assert "gtins" not in attrs and not attrs.get("gtin")
    assert "invent" not in str(body).lower()


def test_maps_feed_generator_product_data_keys():
    row = {
        "sku": "ABC-1",
        "optimized_title": "Navy Jacket L",
        "description": "A clean jacket.",
        "link": "https://shop.example.com/products/j?variant=9",
        "image_url": "https://cdn.example/j.jpg",
        "price": "29.00",
        "currency": "USD",
        "availability": "in_stock",
        "brand": "House",
        "color": "Navy",
        "size": "L",
        "item_group_id": "222",
        "identifier_exists": "no",
        "gtin": "",
    }
    body = feed_row_to_product_input(row, content_language="en", feed_label="US")
    assert body["offerId"] == "ABC-1"
    attrs = body["productAttributes"]
    assert attrs["title"] == "Navy Jacket L"
    assert attrs["imageLink"] == "https://cdn.example/j.jpg"
    assert attrs["price"]["amountMicros"] == "29000000"
    assert "gtins" not in attrs


def test_passes_through_real_gtin_only():
    row = {
        "sku": "G1",
        "title": "Tee",
        "链接": "https://shop.example.com/p",
        "image_link": "https://cdn.example/t.jpg",
        "price": "10 USD",
        "brand": "Acme",
        "identifier_exists": "yes",
        "gtin": "012345678905",
    }
    attrs = feed_row_to_product_input(row)["productAttributes"]
    assert attrs["identifierExists"] is True
    assert attrs["gtins"] == ["012345678905"]
