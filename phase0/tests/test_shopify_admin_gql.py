"""Admin GraphQL helpers — REST-shaped product mapping for public App Store."""
from adfeed.shopify_admin_gql import product_node_to_rest, shop_node_to_rest, policies_to_rest


def test_product_node_to_rest_numeric_ids_and_options():
    node = {
        "id": "gid://shopify/Product/111",
        "title": "Nude socks",
        "handle": "nude-socks",
        "vendor": "Acme",
        "productType": "Socks",
        "descriptionHtml": "<p>Soft</p>",
        "status": "ACTIVE",
        "createdAt": "2026-01-01T00:00:00Z",
        "tags": ["a", "b"],
        "options": [
            {"name": "Color", "position": 1},
            {"name": "Size", "position": 2},
        ],
        "variants": {
            "nodes": [
                {
                    "id": "gid://shopify/ProductVariant/222",
                    "sku": "SKU-W",
                    "price": "9.90",
                    "inventoryQuantity": 3,
                    "barcode": "123",
                    "selectedOptions": [
                        {"name": "Color", "value": "White"},
                        {"name": "Size", "value": "One Size"},
                    ],
                }
            ]
        },
        "images": {"nodes": [{"id": "gid://shopify/ProductImage/9", "url": "https://cdn.example/a.jpg"}]},
    }
    rest = product_node_to_rest(node)
    assert rest["id"] == "111"
    assert rest["product_type"] == "Socks"
    assert rest["body_html"] == "<p>Soft</p>"
    assert rest["status"] == "active"
    assert rest["images"][0]["src"] == "https://cdn.example/a.jpg"
    v = rest["variants"][0]
    assert v["id"] == "222"
    assert v["option1"] == "White"
    assert v["option2"] == "One Size"
    assert v["inventory_quantity"] == 3


def test_product_node_to_rest_variants_count():
    node = {
        "id": "gid://shopify/Product/1",
        "title": "Dress",
        "handle": "dress",
        "vendor": "Acme",
        "productType": "Dress",
        "status": "ACTIVE",
        "options": [],
        "variantsCount": {"count": 42},
        "variants": {"nodes": []},
        "images": {"nodes": []},
    }
    rest = product_node_to_rest(node)
    assert rest["total_variant_count"] == 42


def test_product_list_fields_omit_description():
    from adfeed.shopify_admin_gql import PRODUCT_LIST_FIELDS

    assert "descriptionHtml" not in PRODUCT_LIST_FIELDS
    assert "images(first: 1)" in PRODUCT_LIST_FIELDS
    assert "variantsCount" in PRODUCT_LIST_FIELDS


def test_shop_node_to_rest_currency():
    shop = shop_node_to_rest(
        {
            "name": "Demo",
            "myshopifyDomain": "demo.myshopify.com",
            "primaryDomain": {"url": "https://demo.com"},
            "email": "a@b.com",
            "currencyCode": "USD",
        }
    )
    assert shop["name"] == "Demo"
    assert shop["myshopify_domain"] == "demo.myshopify.com"
    assert shop["currency"] == "USD"
    assert shop["domain"] == "demo.com"


def test_policies_to_rest_maps_type():
    rows = policies_to_rest(
        [
            {
                "type": "PRIVACY_POLICY",
                "title": "Privacy",
                "body": "x" * 120,
                "url": "https://s.com/policies/privacy-policy",
            }
        ]
    )
    assert rows[0]["handle"] == "privacy-policy"
    assert rows[0]["body"].startswith("x")
