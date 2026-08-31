"""High-quality multi-category mock Shopify catalog (local tests only).

Never use the merchant's real myshopify domain. Seed into a fake store such as
`adfeed-mock.myshopify.com` so App Store review / live shops stay untouched.

Field contract:
- color = pure color only (no Style / Floral stuffed into color)
- brand = confirmed mock ad brand ``Northline`` (never silent eprolo)
- no fake GTIN / barcode / COGS
"""

from __future__ import annotations

from typing import Any

MOCK_SHOP_DOMAIN = "adfeed-mock.myshopify.com"
MOCK_SHOP_NAME = "AdFeed Mock Catalog"
MOCK_AD_BRAND = "Northline"
MOCK_MERCHANT_ID = "mock-merchant-001"
MOCK_META_CATALOG_ID = "mock-meta-catalog-001"
MOCK_TIKTOK_SHOP_ID = "mock-tiktok-shop-001"

# product_type → (gpc_code, gpc_path, default_material, age_group, weight_kg)
_TYPE_META: dict[str, tuple[str, str, str | None, str, float]] = {
    "Pants": ("204", "Apparel & Accessories > Clothing > Pants", "Polyester", "adult", 0.45),
    "Skirts": ("6228", "Apparel & Accessories > Clothing > Skirts", "Cotton", "adult", 0.35),
    "Jackets": ("5598", "Apparel & Accessories > Clothing > Outerwear > Coats & Jackets", "Denim", "adult", 0.85),
    "T-Shirts": ("212", "Apparel & Accessories > Clothing > Shirts & Tops", "Cotton", "adult", 0.2),
    "Dresses": ("2271", "Apparel & Accessories > Clothing > Dresses", "Chiffon", "adult", 0.4),
    "Tops": ("212", "Apparel & Accessories > Clothing > Shirts & Tops", "Satin", "adult", 0.22),
    "Shoes": ("187", "Apparel & Accessories > Shoes", "Leather", "adult", 0.7),
    "Bags": ("3032", "Apparel & Accessories > Handbags, Wallets & Cases", "PU leather", "adult", 0.35),
    "Beauty": ("567", "Health & Beauty > Personal Care", None, "adult", 0.12),
    "Home": ("206", "Home & Garden > Decor", "Linen", "adult", 0.25),
    "Electronics": ("222", "Electronics > Electronics Accessories > Cables", "Nylon", "adult", 0.08),
    "Kids": ("1604", "Apparel & Accessories > Clothing", "Fleece", "kids", 0.3),
    "Socks": ("209", "Apparel & Accessories > Clothing > Underwear & Socks > Socks", "Cotton", "adult", 0.08),
    "Accessories": ("178", "Apparel & Accessories > Clothing Accessories", "Metal", "adult", 0.05),
    "Coats": ("5598", "Apparel & Accessories > Clothing > Outerwear > Coats & Jackets", "Wool", "adult", 1.2),
    "Shorts": ("207", "Apparel & Accessories > Clothing > Shorts", "Linen", "adult", 0.25),
    "Jeans": ("204", "Apparel & Accessories > Clothing > Pants", "Denim", "adult", 0.55),
    "Sweaters": ("212", "Apparel & Accessories > Clothing > Shirts & Tops", "Wool", "adult", 0.4),
    "Activewear": ("5322", "Apparel & Accessories > Clothing > Activewear", "Polyester", "adult", 0.28),
    "Swimwear": ("211", "Apparel & Accessories > Clothing > Swimwear", "Polyester", "adult", 0.18),
    "Underwear": ("213", "Apparel & Accessories > Clothing > Underwear & Socks", "Cotton", "adult", 0.1),
    "Hats": ("173", "Apparel & Accessories > Clothing Accessories > Hats", "Wool", "adult", 0.12),
    "Scarves": ("177", "Apparel & Accessories > Clothing Accessories > Scarves & Shawls", "Cashmere", "adult", 0.15),
    "Gloves": ("170", "Apparel & Accessories > Clothing Accessories > Gloves & Mittens", "Knit", "adult", 0.1),
    "Belts": ("169", "Apparel & Accessories > Clothing Accessories > Belts", "Canvas", "adult", 0.15),
    "Watches": ("201", "Apparel & Accessories > Jewelry > Watches", "Metal", "adult", 0.1),
    "Jewelry": ("188", "Apparel & Accessories > Jewelry", "Metal", "adult", 0.03),
    "Sunglasses": ("178", "Apparel & Accessories > Clothing Accessories", "Metal", "adult", 0.05),
    "Boots": ("187", "Apparel & Accessories > Shoes", "Leather", "adult", 0.9),
    "Sandals": ("187", "Apparel & Accessories > Shoes", "EVA", "adult", 0.35),
    "Backpacks": ("100", "Luggage & Bags > Backpacks", "Nylon", "adult", 0.55),
    "Wallets": ("3032", "Apparel & Accessories > Handbags, Wallets & Cases", "Leather", "adult", 0.1),
    "Luggage": ("101", "Luggage & Bags", "ABS", "adult", 3.2),
    "Kitchen": ("640", "Home & Garden > Kitchen & Dining", "Silicone", "adult", 0.15),
    "Pet": ("2", "Animals & Pet Supplies > Pet Supplies", "Nylon", "adult", 0.2),
    "Sports": ("499799", "Sporting Goods > Exercise & Fitness", "TPE", "adult", 1.1),
    "Office": ("922", "Office Supplies", "Bamboo", "adult", 0.4),
    "Baby": ("1007", "Baby & Toddler > Baby & Toddler Apparel", "Cotton", "infant", 0.12),
    "Toys": ("1239", "Toys & Games > Toys", "Wood", "kids", 0.6),
    "Garden": ("985", "Home & Garden > Lawn & Garden", "Fabric", "adult", 0.15),
}

_HANDLE_OVERRIDES: dict[str, dict[str, Any]] = {
    "linen-throw-pillow": {
        "gpc_code": "206",
        "gpc_path": "Home & Garden > Decor > Throw Pillows",
        "material": "Linen",
        "description": "Envelope-style linen pillow cover; insert not included. Soft cream or gray options.",
        "weight_kg": 0.2,
    },
    "ceramic-mug": {
        "gpc_code": "672",
        "gpc_path": "Home & Garden > Kitchen & Dining > Tableware > Drinkware > Mugs",
        "material": "Stoneware",
        "description": "Durable stoneware mug, dishwasher safe, 350ml.",
        "weight_kg": 0.35,
    },
    "silicone-spatula": {
        "gpc_code": "668",
        "gpc_path": "Home & Garden > Kitchen & Dining > Kitchen Tools & Utensils",
        "material": "Silicone",
        "description": "Heat-resistant silicone spatula set for nonstick cookware.",
        "weight_kg": 0.12,
    },
    "usbc-nylon-cable": {
        "gpc_code": "259",
        "gpc_path": "Electronics > Electronics Accessories > Cables > Data Transfer Cables",
        "material": "Nylon",
        "description": "Braided USB-C charging and data cable, 1 meter.",
        "weight_kg": 0.05,
    },
    "minimal-watch": {
        "gpc_code": "201",
        "gpc_path": "Apparel & Accessories > Jewelry > Watches",
        "material": "Stainless Steel",
        "description": "Minimal analog wristwatch with stainless case.",
        "weight_kg": 0.08,
    },
    "sunscreen-lotion": {
        "gpc_code": "567",
        "gpc_path": "Health & Beauty > Personal Care > Cosmetics > Skin Care > Sunscreen",
        "material": None,
        "description": "Broad-spectrum SPF 50 sunscreen lotion, 50ml. No medical claims.",
        "weight_kg": 0.08,
    },
    "lip-balm": {
        "gpc_code": "567",
        "gpc_path": "Health & Beauty > Personal Care > Cosmetics > Makeup > Lip Makeup",
        "material": None,
        "description": "Tinted moisturizing lip balm in rose or nude.",
        "weight_kg": 0.02,
    },
    "dog-leash": {
        "gpc_code": "2",
        "gpc_path": "Animals & Pet Supplies > Pet Supplies > Dog Supplies > Dog Leashes",
        "material": "Nylon",
        "description": "Nylon dog leash with metal clip, 120cm.",
        "weight_kg": 0.18,
    },
    "yoga-mat": {
        "gpc_code": "499799",
        "gpc_path": "Sporting Goods > Exercise & Fitness > Yoga & Pilates > Yoga Mats",
        "material": "TPE",
        "description": "Non-slip TPE yoga mat for studio and home practice.",
        "weight_kg": 1.0,
    },
    "baby-bodysuit": {
        "gpc_code": "1007",
        "gpc_path": "Baby & Toddler > Baby & Toddler Apparel > Baby One-Pieces",
        "material": "Organic cotton",
        "age_group": "infant",
        "description": "Soft organic cotton baby bodysuit with snap closures.",
        "weight_kg": 0.1,
    },
    "wooden-blocks": {
        "gpc_code": "1239",
        "gpc_path": "Toys & Games > Toys > Building Toys",
        "material": "Wood",
        "age_group": "kids",
        "description": "Natural wood building blocks for creative play.",
        "weight_kg": 0.55,
    },
    "kids-hoodie": {
        "age_group": "kids",
        "gpc_code": "1604",
        "gpc_path": "Apparel & Accessories > Clothing",
        "material": "Fleece",
        "description": "Soft fleece hoodie with kangaroo pocket for kids.",
        "weight_kg": 0.28,
    },
    "wool-overcoat": {
        "material": "Wool",
        "description": "Classic wool overcoat with notch lapel for cool weather.",
        "weight_kg": 1.15,
    },
    "slim-jeans": {
        "material": "Denim",
        "description": "Slim stretch denim jeans with mid rise.",
        "weight_kg": 0.55,
    },
    "gap-missing-color-tee": {
        "description": "Relaxed-fit cotton tee used to exercise missing-color tips in QA.",
        "material": "Cotton",
        "weight_kg": 0.18,
    },
    "gap-missing-image-socks": {
        "description": "Crew socks 3-pack — image omitted on purpose for GMC image-issue mocks.",
        "material": "Cotton",
        "weight_kg": 0.1,
    },
    "gap-zero-price-pin": {
        "description": "Enamel lapel pin used as a zero-price quality-gate edge case.",
        "material": "Metal",
        "weight_kg": 0.02,
    },
    "gap-oos-belt": {
        "description": "Leather belt kept out-of-stock for availability sync tests.",
        "material": "Leather",
        "weight_kg": 0.2,
    },
}

# Stable Shopify-like numeric ids for re-seed idempotency.
_CATALOG: list[dict[str, Any]] = [
    # ── Apparel: pants / skirt / jacket (field-contract self-check trio) ──
    {
        "shopify_product_id": "9001001",
        "handle": "wide-leg-trousers",
        "title": "High-Waist Wide-Leg Trousers",
        "product_type": "Pants",
        "vendor": "1688 Factory A",
        "material": "Polyester",
        "gender": "female",
        "age_group": "adult",
        "description": "Soft drape wide-leg trousers with high waist and side pockets.",
        "image_url": "https://images.example.com/mock/wide-leg-trousers.jpg",
        "variants": [
            {"sku": "NL-PANT-BLK-S", "color": "Black", "size": "S", "price": 39.9, "inventory": 12},
            {"sku": "NL-PANT-BLK-M", "color": "Black", "size": "M", "price": 39.9, "inventory": 20},
            {"sku": "NL-PANT-KHK-M", "color": "Khaki", "size": "M", "price": 39.9, "inventory": 8},
            {"sku": "NL-PANT-KHK-L", "color": "Khaki", "size": "L", "price": 39.9, "inventory": 6},
        ],
    },
    {
        "shopify_product_id": "9001002",
        "handle": "midi-a-line-skirt",
        "title": "A-Line Midi Skirt",
        "product_type": "Skirts",
        "vendor": "1688 Factory A",
        "material": "Cotton blend",
        "gender": "female",
        "age_group": "adult",
        "description": "Knee-length A-line midi skirt with invisible side zip.",
        "image_url": "https://images.example.com/mock/midi-a-line-skirt.jpg",
        "variants": [
            {"sku": "NL-SKIRT-NVY-S", "color": "Navy", "size": "S", "price": 34.5, "inventory": 10},
            {"sku": "NL-SKIRT-NVY-M", "color": "Navy", "size": "M", "price": 34.5, "inventory": 14},
            {"sku": "NL-SKIRT-CRM-M", "color": "Cream", "size": "M", "price": 34.5, "inventory": 9},
        ],
    },
    {
        "shopify_product_id": "9001003",
        "handle": "classic-denim-jacket",
        "title": "Classic Denim Jacket",
        "product_type": "Jackets",
        "vendor": "1688 Factory B",
        "material": "Denim",
        "gender": "unisex",
        "age_group": "adult",
        "description": "Washed denim jacket with chest pockets and metal buttons.",
        "image_url": "https://images.example.com/mock/classic-denim-jacket.jpg",
        "variants": [
            {"sku": "NL-JKT-BLU-S", "color": "Blue", "size": "S", "price": 59.0, "inventory": 7},
            {"sku": "NL-JKT-BLU-M", "color": "Blue", "size": "M", "price": 59.0, "inventory": 15},
            {"sku": "NL-JKT-BLU-L", "color": "Blue", "size": "L", "price": 59.0, "inventory": 11},
            {"sku": "NL-JKT-BLU-XL", "color": "Blue", "size": "XL", "price": 59.0, "inventory": 4},
        ],
    },
    {
        "shopify_product_id": "9001004",
        "handle": "cotton-crew-tee",
        "title": "Organic Cotton Crew Tee",
        "product_type": "T-Shirts",
        "vendor": "1688 Factory B",
        "material": "Organic cotton",
        "gender": "unisex",
        "age_group": "adult",
        "description": "Everyday crew-neck tee in midweight organic cotton.",
        "image_url": "https://images.example.com/mock/cotton-crew-tee.jpg",
        "variants": [
            {"sku": "NL-TEE-WHT-S", "color": "White", "size": "S", "price": 18.0, "inventory": 30},
            {"sku": "NL-TEE-WHT-M", "color": "White", "size": "M", "price": 18.0, "inventory": 40},
            {"sku": "NL-TEE-BLK-M", "color": "Black", "size": "M", "price": 18.0, "inventory": 35},
            {"sku": "NL-TEE-BLK-L", "color": "Black", "size": "L", "price": 18.0, "inventory": 22},
        ],
    },
    {
        "shopify_product_id": "9001005",
        "handle": "pink-floral-midi-dress",
        "title": "Pink Floral Midi Dress",
        "product_type": "Dresses",
        "vendor": "1688 Factory C",
        "material": "Chiffon",
        "gender": "female",
        "age_group": "adult",
        "description": "Soft chiffon midi dress with floral print; color is pink only.",
        "image_url": "https://images.example.com/mock/pink-floral-midi-dress.jpg",
        # color stays Pink — floral is print language in title, not stuffed into color
        "variants": [
            {"sku": "NL-DRS-PNK-S", "color": "Pink", "size": "S", "price": 48.0, "inventory": 6},
            {"sku": "NL-DRS-PNK-M", "color": "Pink", "size": "M", "price": 48.0, "inventory": 10},
            {"sku": "NL-DRS-PNK-L", "color": "Pink", "size": "L", "price": 48.0, "inventory": 5},
        ],
    },
    {
        "shopify_product_id": "9001006",
        "handle": "wrap-blouse",
        "title": "Satin Wrap Blouse",
        "product_type": "Tops",
        "vendor": "1688 Factory C",
        "material": "Satin",
        "gender": "female",
        "age_group": "adult",
        "description": "V-neck wrap blouse with tie waist.",
        "image_url": "https://images.example.com/mock/wrap-blouse.jpg",
        "variants": [
            {"sku": "NL-BLS-IVO-S", "color": "Ivory", "size": "S", "price": 32.0, "inventory": 8},
            {"sku": "NL-BLS-IVO-M", "color": "Ivory", "size": "M", "price": 32.0, "inventory": 12},
            {"sku": "NL-BLS-EMR-M", "color": "Emerald", "size": "M", "price": 32.0, "inventory": 7},
        ],
    },
    # ── Shoes ──
    {
        "shopify_product_id": "9002001",
        "handle": "leather-sneakers",
        "title": "Low-Top Leather Sneakers",
        "product_type": "Shoes",
        "vendor": "1688 Factory D",
        "material": "Leather",
        "gender": "unisex",
        "age_group": "adult",
        "description": "Minimal low-top sneakers with rubber sole.",
        "image_url": "https://images.example.com/mock/leather-sneakers.jpg",
        "variants": [
            {"sku": "NL-SNK-WHT-37", "color": "White", "size": "37", "price": 69.0, "inventory": 5},
            {"sku": "NL-SNK-WHT-38", "color": "White", "size": "38", "price": 69.0, "inventory": 9},
            {"sku": "NL-SNK-WHT-39", "color": "White", "size": "39", "price": 69.0, "inventory": 8},
            {"sku": "NL-SNK-BLK-38", "color": "Black", "size": "38", "price": 69.0, "inventory": 6},
        ],
    },
    # ── Bags ──
    {
        "shopify_product_id": "9003001",
        "handle": "crossbody-bag",
        "title": "Mini Crossbody Bag",
        "product_type": "Bags",
        "vendor": "1688 Factory D",
        "material": "PU leather",
        "gender": "female",
        "age_group": "adult",
        "description": "Compact crossbody with adjustable strap.",
        "image_url": "https://images.example.com/mock/crossbody-bag.jpg",
        "variants": [
            {"sku": "NL-BAG-BRN-OS", "color": "Brown", "size": "One Size", "price": 28.0, "inventory": 18},
            {"sku": "NL-BAG-BLK-OS", "color": "Black", "size": "One Size", "price": 28.0, "inventory": 21},
        ],
    },
    # ── Beauty ──
    {
        "shopify_product_id": "9004001",
        "handle": "daily-moisturizer",
        "title": "Daily Gel Moisturizer 50ml",
        "product_type": "Beauty",
        "vendor": "1688 Factory E",
        "material": None,
        "gender": "unisex",
        "age_group": "adult",
        "description": "Lightweight gel moisturizer for daily use. No medical claims.",
        "image_url": "https://images.example.com/mock/daily-moisturizer.jpg",
        "variants": [
            {"sku": "NL-BTY-MOI-50", "color": None, "size": "50ml", "price": 22.0, "inventory": 40},
        ],
    },
    # ── Home ──
    {
        "shopify_product_id": "9005001",
        "handle": "linen-throw-pillow",
        "title": "Linen Throw Pillow Cover",
        "product_type": "Home",
        "vendor": "1688 Factory E",
        "material": "Linen",
        "gender": None,
        "age_group": None,
        "description": "Envelope-style linen pillow cover, insert not included.",
        "image_url": "https://images.example.com/mock/linen-throw-pillow.jpg",
        "variants": [
            {"sku": "NL-HM-PIL-CRM", "color": "Cream", "size": "45x45cm", "price": 16.0, "inventory": 25},
            {"sku": "NL-HM-PIL-GRY", "color": "Gray", "size": "45x45cm", "price": 16.0, "inventory": 19},
        ],
    },
    # ── Electronics accessory ──
    {
        "shopify_product_id": "9006001",
        "handle": "usbc-nylon-cable",
        "title": "USB-C Nylon Charging Cable 1m",
        "product_type": "Electronics",
        "vendor": "1688 Factory F",
        "material": "Nylon",
        "gender": None,
        "age_group": None,
        "description": "Braided USB-C cable, 1 meter.",
        "image_url": "https://images.example.com/mock/usbc-nylon-cable.jpg",
        "variants": [
            {"sku": "NL-ELC-CBL-BLK", "color": "Black", "size": "1m", "price": 9.9, "inventory": 100},
        ],
    },
    # ── Kids ──
    {
        "shopify_product_id": "9007001",
        "handle": "kids-hoodie",
        "title": "Kids Fleece Hoodie",
        "product_type": "Kids",
        "vendor": "1688 Factory F",
        "material": "Fleece",
        "gender": "unisex",
        "age_group": "kids",
        "description": "Soft fleece hoodie with kangaroo pocket.",
        "image_url": "https://images.example.com/mock/kids-hoodie.jpg",
        "variants": [
            {"sku": "NL-KID-HD-RED-6", "color": "Red", "size": "6Y", "price": 24.0, "inventory": 10},
            {"sku": "NL-KID-HD-RED-8", "color": "Red", "size": "8Y", "price": 24.0, "inventory": 12},
            {"sku": "NL-KID-HD-NVY-8", "color": "Navy", "size": "8Y", "price": 24.0, "inventory": 9},
        ],
    },
    # ── Intentional gaps (UI tip / GMC issue targets — still no fake GTIN) ──
    {
        "shopify_product_id": "9008001",
        "handle": "gap-missing-color-tee",
        "title": "Relaxed Fit Tee",
        "product_type": "T-Shirts",
        "vendor": "1688 Factory G",
        "material": "Cotton",
        "gender": "unisex",
        "age_group": "adult",
        "description": "Relaxed tee used to exercise missing-color tips.",
        "image_url": "https://images.example.com/mock/gap-missing-color-tee.jpg",
        "variants": [
            {"sku": "NL-GAP-TEE-M", "color": None, "size": "M", "price": 15.0, "inventory": 3},
        ],
    },
    {
        "shopify_product_id": "9008002",
        "handle": "gap-missing-image-socks",
        "title": "Crew Socks 3-Pack",
        "product_type": "Socks",
        "vendor": "1688 Factory G",
        "material": "Cotton",
        "gender": "unisex",
        "age_group": "adult",
        "description": "Crew socks pack — product image omitted for GMC image issue mock.",
        "image_url": None,
        "variants": [
            {
                "sku": "NL-GAP-SOCK-OS",
                "color": "Gray",
                "size": "One Size",
                "price": 12.0,
                "inventory": 50,
                "image_url": None,
            },
        ],
    },
    {
        "shopify_product_id": "9008003",
        "handle": "gap-zero-price-pin",
        "title": "Enamel Lapel Pin",
        "product_type": "Accessories",
        "vendor": "1688 Factory G",
        "material": "Metal",
        "gender": "unisex",
        "age_group": "adult",
        "description": "Zero-price edge case for quality gate tests.",
        "image_url": "https://images.example.com/mock/gap-zero-price-pin.jpg",
        "variants": [
            {"sku": "NL-GAP-PIN-OS", "color": "Gold", "size": "One Size", "price": 0, "inventory": 2},
        ],
    },
    {
        "shopify_product_id": "9008004",
        "handle": "gap-oos-belt",
        "title": "Leather Belt",
        "product_type": "Accessories",
        "vendor": "1688 Factory G",
        "material": "Leather",
        "gender": "unisex",
        "age_group": "adult",
        "description": "Out-of-stock edge case.",
        "image_url": "https://images.example.com/mock/gap-oos-belt.jpg",
        "variants": [
            {"sku": "NL-GAP-BELT-BRN", "color": "Brown", "size": "M", "price": 19.0, "inventory": 0},
        ],
    },
]

# Compact extras → dozens of SKUs across more categories (still pure colors, no GTIN).
_EXTRA_SPECS: list[tuple[str, str, str, list[str], list[str], float]] = [
    # product_type, handle_slug, title, colors, sizes, price
    ("Coats", "wool-overcoat", "Wool Overcoat", ["Camel", "Black"], ["S", "M", "L"], 129.0),
    ("Shorts", "linen-shorts", "Linen Bermuda Shorts", ["Beige", "Olive"], ["S", "M", "L"], 29.0),
    ("Jeans", "slim-jeans", "Slim Stretch Jeans", ["Blue", "Black"], ["28", "30", "32", "34"], 49.0),
    ("Sweaters", "crew-sweater", "Merino Crew Sweater", ["Charcoal", "Cream"], ["S", "M", "L", "XL"], 55.0),
    ("Activewear", "yoga-leggings", "High-Rise Yoga Leggings", ["Black", "Plum"], ["XS", "S", "M", "L"], 35.0),
    ("Swimwear", "one-piece-swimsuit", "One-Piece Swimsuit", ["Navy", "Red"], ["S", "M", "L"], 42.0),
    ("Underwear", "cotton-briefs", "Cotton Briefs 3-Pack", ["Black", "White"], ["M", "L"], 14.0),
    ("Hats", "wool-beanie", "Wool Beanie", ["Gray", "Forest"], ["One Size"], 16.0),
    ("Scarves", "cashmere-scarf", "Cashmere Scarf", ["Ivory", "Burgundy"], ["One Size"], 38.0),
    ("Gloves", "touchscreen-gloves", "Touchscreen Knit Gloves", ["Black"], ["S", "M", "L"], 18.0),
    ("Belts", "canvas-belt", "Canvas Web Belt", ["Khaki", "Navy"], ["S", "M", "L"], 15.0),
    ("Watches", "minimal-watch", "Minimal Analog Watch", ["Silver", "Black"], ["One Size"], 79.0),
    ("Jewelry", "hoop-earrings", "Gold Hoop Earrings", ["Gold"], ["One Size"], 24.0),
    ("Sunglasses", "aviator-sunglasses", "Aviator Sunglasses", ["Gold", "Black"], ["One Size"], 27.0),
    ("Boots", "chelsea-boots", "Chelsea Ankle Boots", ["Black", "Brown"], ["38", "39", "40", "41"], 89.0),
    ("Sandals", "slide-sandals", "Comfort Slide Sandals", ["White", "Black"], ["36", "37", "38", "39"], 22.0),
    ("Backpacks", "day-backpack", "Everyday Daypack", ["Olive", "Black"], ["One Size"], 45.0),
    ("Wallets", "bifold-wallet", "Bifold Card Wallet", ["Brown", "Black"], ["One Size"], 21.0),
    ("Luggage", "carry-on-spinner", "Carry-On Spinner", ["Navy"], ["One Size"], 119.0),
    ("Beauty", "lip-balm", "Tinted Lip Balm", ["Rose", "Nude"], ["One Size"], 8.0),
    ("Beauty", "sunscreen-lotion", "SPF 50 Sunscreen Lotion", [None], ["50ml"], 19.0),
    ("Home", "ceramic-mug", "Stoneware Mug", ["White", "Sage"], ["350ml"], 12.0),
    ("Home", "cotton-duvet-cover", "Cotton Duvet Cover", ["White", "Sage"], ["Queen"], 64.0),
    ("Kitchen", "silicone-spatula", "Silicone Spatula Set", ["Coral"], ["One Size"], 11.0),
    ("Pet", "dog-leash", "Nylon Dog Leash", ["Red", "Blue"], ["120cm"], 13.0),
    ("Sports", "yoga-mat", "Non-Slip Yoga Mat", ["Purple", "Teal"], ["One Size"], 28.0),
    ("Office", "desk-organizer", "Bamboo Desk Organizer", ["Natural"], ["One Size"], 23.0),
    ("Baby", "baby-bodysuit", "Organic Baby Bodysuit", ["White", "Mint"], ["0-3M", "3-6M"], 17.0),
    ("Toys", "wooden-blocks", "Wooden Building Blocks", ["Natural"], ["One Size"], 26.0),
    ("Garden", "garden-gloves", "Gardening Gloves", ["Green"], ["M", "L"], 9.0),
]


def _build_extra_catalog() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, (ptype, handle, title, colors, sizes, price) in enumerate(_EXTRA_SPECS):
        pid = str(9010000 + idx)
        variants = []
        for ci, color in enumerate(colors):
            for si, size in enumerate(sizes):
                color_code = (color or "NA")[:3].upper()
                size_code = str(size).replace(" ", "").replace("-", "")[:6].upper()
                sku = f"NL-X{idx:02d}-{color_code}-{size_code}"
                variants.append(
                    {
                        "sku": sku,
                        "color": color,
                        "size": size,
                        "price": price,
                        "inventory": 5 + (ci + si) % 7,
                    }
                )
        out.append(
            {
                "shopify_product_id": pid,
                "handle": handle,
                "title": title,
                "product_type": ptype,
                "vendor": f"1688 Factory X{idx % 5}",
                "material": None,
                "gender": "unisex",
                "age_group": "adult",
                "description": f"{title} — quality everyday product from the Northline mock catalog.",
                "image_url": f"https://images.example.com/mock/{handle}.jpg",
                "variants": variants,
            }
        )
    return out


def _enrich_product(item: dict[str, Any]) -> dict[str, Any]:
    """Attach GPC / material / age / weight / real description (owner layer)."""
    ptype = item.get("product_type") or ""
    handle = item.get("handle") or ""
    meta = _TYPE_META.get(ptype)
    if meta:
        code, path, mat, age, wkg = meta
        item.setdefault("gpc_code", code)
        item.setdefault("gpc_path", path)
        if item.get("material") in (None, ""):
            item["material"] = mat
        if not item.get("age_group"):
            item["age_group"] = age
        item.setdefault("weight_kg", wkg)
    ov = _HANDLE_OVERRIDES.get(handle) or {}
    item.update({k: v for k, v in ov.items() if v is not None or k == "material"})
    # Clear test blurb if still present
    desc = item.get("description") or ""
    if "mock catalog SKU" in desc.lower():
        item["description"] = ov.get("description") or f"{item.get('title')}. Ready for shopping ads."
    item["gpc_source"] = "catalog"
    item["gpc_confidence"] = 0.95
    wkg = float(item.get("weight_kg") or 0) or None
    if wkg:
        for v in item.get("variants") or []:
            v.setdefault("weight", wkg)
            v.setdefault("weight_unit", "kg")
    return item


def catalog_products() -> list[dict[str, Any]]:
    """Return a deep-ish copy of the catalog definitions."""
    import copy

    return [_enrich_product(p) for p in copy.deepcopy(_CATALOG + _build_extra_catalog())]


def catalog_stats() -> dict[str, Any]:
    products = catalog_products()
    skus = [v["sku"] for p in products for v in p["variants"]]
    types = sorted({p["product_type"] for p in products})
    return {
        "products": len(products),
        "variants": len(skus),
        "product_types": types,
        "skus": skus,
        "brand": MOCK_AD_BRAND,
        "domain": MOCK_SHOP_DOMAIN,
    }


def mock_gmc_issues() -> list[dict[str, Any]]:
    """Synthetic Merchant issues: many reason codes + matched/unmatched offers."""
    return [
        # image family
        {"offer_id": "NL-GAP-SOCK-OS", "status": "disapproved", "reason_code": "image_missing", "reason_text": "Missing product image"},
        {"offer_id": "NL-X00-CAM-S", "status": "disapproved", "reason_code": "image_too_small", "reason_text": "Image resolution too low"},
        {"offer_id": "NL-X01-BEI-M", "status": "disapproved", "reason_code": "picture_blurry", "reason_text": "Blurry picture"},
        {"offer_id": "NL-X02-BLU-30", "status": "disapproved", "reason_code": "photo_watermark", "reason_text": "Watermark detected"},
        # color / size
        {"offer_id": "NL-GAP-TEE-M", "status": "disapproved", "reason_code": "missing_color", "reason_text": "Color attribute missing"},
        {"offer_id": "NL-X03-CHA-M", "status": "disapproved", "reason_code": "invalid_color", "reason_text": "Color not recognized"},
        {"offer_id": "NL-X04-BLA-S", "status": "disapproved", "reason_code": "missing_size", "reason_text": "Size missing"},
        {"offer_id": "NL-X05-NAV-M", "status": "disapproved", "reason_code": "soft_size_mismatch", "reason_text": "Size mismatch"},
        # brand
        {"offer_id": "NL-JKT-BLU-M", "status": "disapproved", "reason_code": "invalid_brand", "reason_text": "Brand does not match"},
        {"offer_id": "NL-PANT-BLK-M", "status": "disapproved", "reason_code": "missing_brand", "reason_text": "Brand required"},
        {"offer_id": "NL-TEE-WHT-M", "status": "disapproved", "reason_code": "brand_mismatch", "reason_text": "Brand mismatch"},
        # identifier / gtin → view_only (never invent)
        {"offer_id": "NL-BAG-BRN-OS", "status": "disapproved", "reason_code": "missing_gtin", "reason_text": "GTIN missing"},
        {"offer_id": "NL-SNK-WHT-38", "status": "disapproved", "reason_code": "invalid_identifier", "reason_text": "Bad identifier"},
        {"offer_id": "NL-BTY-MOI-50", "status": "disapproved", "reason_code": "gtin_conflict", "reason_text": "GTIN conflict"},
        # approved / soft
        {"offer_id": "NL-SKIRT-NVY-M", "status": "approved", "reason_code": "", "reason_text": ""},
        {"offer_id": "NL-DRS-PNK-M", "status": "approved", "reason_code": "", "reason_text": ""},
        {"offer_id": "NL-X06-BLA-M", "status": "pending", "reason_code": "under_review", "reason_text": "Pending review"},
        # price / policy / other → view_only
        {"offer_id": "NL-GAP-PIN-OS", "status": "disapproved", "reason_code": "price_mismatch", "reason_text": "Landing page price differs"},
        {"offer_id": "NL-GAP-BELT-BRN", "status": "disapproved", "reason_code": "out_of_stock", "reason_text": "Item unavailable"},
        {"offer_id": "NL-X12-GOL-ONESIZ", "status": "disapproved", "reason_code": "policy_violation", "reason_text": "Policy"},
        {"offer_id": "NL-ELC-CBL-BLK", "status": "disapproved", "reason_code": "landing_page_error", "reason_text": "404 on PDP"},
        {"offer_id": "NL-HM-PIL-CRM", "status": "disapproved", "reason_code": "shipping_issue", "reason_text": "Shipping not set"},
        # unmatched offers
        {"offer_id": "UNKNOWN-OFFER-999", "status": "disapproved", "reason_code": "other", "reason_text": "Unmatched offer"},
        {"offer_id": "GHOST-SKU-001", "status": "disapproved", "reason_code": "image_missing", "reason_text": "Ghost image issue"},
        {"offer_id": "GHOST-SKU-002", "status": "disapproved", "reason_code": "missing_color", "reason_text": "Ghost color issue"},
    ]


def mock_meta_issues() -> list[dict[str, Any]]:
    """Synthetic Meta Commerce catalog issues (offer_id == feed SKU)."""
    return [
        {"offer_id": "NL-GAP-SOCK-OS", "status": "disapproved", "reason_code": "image_missing", "reason_text": "Meta: missing image"},
        {"offer_id": "NL-GAP-TEE-M", "status": "disapproved", "reason_code": "missing_color", "reason_text": "Meta: color required"},
        {"offer_id": "NL-JKT-BLU-M", "status": "disapproved", "reason_code": "invalid_brand", "reason_text": "Meta: brand issue"},
        {"offer_id": "NL-BAG-BRN-OS", "status": "disapproved", "reason_code": "missing_gtin", "reason_text": "Meta: identifier"},
        {"offer_id": "NL-PANT-BLK-M", "status": "approved", "reason_code": "", "reason_text": ""},
        {"offer_id": "NL-SKIRT-NVY-M", "status": "approved", "reason_code": "", "reason_text": ""},
        {"offer_id": "NL-DRS-PNK-M", "status": "disapproved", "reason_code": "image_link_broken", "reason_text": "Meta: bad image URL"},
        {"offer_id": "NL-X04-BLA-S", "status": "disapproved", "reason_code": "missing_size", "reason_text": "Meta: size"},
        {"offer_id": "NL-GAP-PIN-OS", "status": "disapproved", "reason_code": "price_mismatch", "reason_text": "Meta: price"},
        {"offer_id": "NL-X00-CAM-S", "status": "disapproved", "reason_code": "photo_quality", "reason_text": "Meta: photo"},
        {"offer_id": "META-GHOST-001", "status": "disapproved", "reason_code": "other", "reason_text": "Unmatched Meta offer"},
        {"offer_id": "META-GHOST-002", "status": "disapproved", "reason_code": "missing_color", "reason_text": "Unmatched Meta color"},
    ]


def mock_tiktok_issues() -> list[dict[str, Any]]:
    """Synthetic TikTok Shop product issues (offer_id == feed SKU)."""
    return [
        {"offer_id": "NL-GAP-SOCK-OS", "status": "disapproved", "reason_code": "image_missing", "reason_text": "TikTok: missing image"},
        {"offer_id": "NL-GAP-TEE-M", "status": "disapproved", "reason_code": "missing_color", "reason_text": "TikTok: color"},
        {"offer_id": "NL-JKT-BLU-M", "status": "disapproved", "reason_code": "brand_required", "reason_text": "TikTok: brand"},
        {"offer_id": "NL-SNK-WHT-38", "status": "disapproved", "reason_code": "invalid_identifier", "reason_text": "TikTok: id"},
        {"offer_id": "NL-PANT-BLK-M", "status": "approved", "reason_code": "", "reason_text": ""},
        {"offer_id": "NL-SKIRT-NVY-M", "status": "approved", "reason_code": "", "reason_text": ""},
        {"offer_id": "NL-X02-BLU-30", "status": "disapproved", "reason_code": "category_mismatch", "reason_text": "TikTok: category"},
        {"offer_id": "NL-X05-NAV-M", "status": "disapproved", "reason_code": "soft_size_mismatch", "reason_text": "TikTok: size"},
        {"offer_id": "NL-GAP-BELT-BRN", "status": "disapproved", "reason_code": "out_of_stock", "reason_text": "TikTok: stock"},
        {"offer_id": "NL-ELC-CBL-BLK", "status": "disapproved", "reason_code": "landing_page_error", "reason_text": "TikTok: PDP"},
        {"offer_id": "TT-GHOST-001", "status": "disapproved", "reason_code": "image_missing", "reason_text": "Unmatched TT image"},
        {"offer_id": "TT-GHOST-002", "status": "disapproved", "reason_code": "policy_violation", "reason_text": "Unmatched TT policy"},
    ]


def seed_mock_catalog(store_db, store_id: str) -> dict[str, Any]:
    """Upsert catalog products/variants into an existing store. No Shopify API."""
    product_ids: list[str] = []
    skus: list[str] = []
    for i, item in enumerate(catalog_products()):
        product = store_db.save_product(
            store_id,
            title=item["title"],
            shopify_product_id=item["shopify_product_id"],
            handle=item["handle"],
            vendor=item.get("vendor"),
            product_type=item.get("product_type"),
            brand=MOCK_AD_BRAND,
            material=item.get("material"),
            gender=item.get("gender"),
            age_group=item.get("age_group"),
            description=item.get("description"),
            image_url=item.get("image_url"),
            gpc_code=item.get("gpc_code"),
            gpc_path=item.get("gpc_path"),
            gpc_confidence=item.get("gpc_confidence", 0.95),
            gpc_source=item.get("gpc_source") or "catalog",
            status="active",
            ai_status="raw",
        )
        product_ids.append(product.id)
        for j, var in enumerate(item["variants"]):
            img = var.get("image_url", item.get("image_url"))
            store_db.save_variant(
                product.id,
                sku=var["sku"],
                shopify_variant_id=str(9100000 + i * 100 + j),
                title=f"{item['title']} / {var.get('color') or '—'} / {var.get('size') or '—'}",
                color=var.get("color"),
                size=var.get("size"),
                price=var.get("price", 0),
                inventory=var.get("inventory", 0),
                image_url=img,
                barcode=None,
                weight=var.get("weight"),
                weight_unit=var.get("weight_unit") or "kg",
                status="active",
            )
            skus.append(var["sku"])
    return {
        "store_id": store_id,
        "product_ids": product_ids,
        "skus": skus,
        "brand": MOCK_AD_BRAND,
        "gmc_issues": mock_gmc_issues(),
        "meta_issues": mock_meta_issues(),
        "tiktok_issues": mock_tiktok_issues(),
        "stats": catalog_stats(),
    }


def ensure_mock_store(store_db, *, create_user, get_user_by_email=None):
    """Create or refresh the dedicated mock store (never the merchant's real shop)."""
    from adfeed.db import get_user_by_email as _get

    getter = get_user_by_email or _get
    user = getter("mock-catalog@adfeed.ai") or create_user(
        email="mock-catalog@adfeed.ai",
        name="Mock Catalog",
    )
    store = store_db.get_store_by_domain(MOCK_SHOP_DOMAIN)
    if store:
        store_db.update_store(
            store.id,
            shop_name=MOCK_SHOP_NAME,
            default_brand=MOCK_AD_BRAND,
            status="active",
            plan="growth",
            quota_total=max(store.quota_total or 0, 500),
            access_token="shpat_mock_local_only",
        )
        store = store_db.get_store(store.id)
    else:
        store = store_db.create_store(
            user_id=user.id,
            shopify_domain=MOCK_SHOP_DOMAIN,
            shop_name=MOCK_SHOP_NAME,
            access_token="shpat_mock_local_only",
            plan="growth",
            quota_total=500,
        )
        store_db.update_store(store.id, default_brand=MOCK_AD_BRAND)
        store = store_db.get_store(store.id)
    seeded = seed_mock_catalog(store_db, store.id)
    return store, seeded
