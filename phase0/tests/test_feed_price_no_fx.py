"""Feed submit path must not FX-convert prices."""
import pandas as pd

from adfeed.feed_generator import generate


def test_generate_uses_row_currency_without_fx():
    df = pd.DataFrame([{
        "SKU": "sku-1",
        "优化后标题": "Test Dress",
        "标题": "Test Dress",
        "描述": "A nice dress for testing feed currency.",
        "GPC代码": "2271",
        "GPC路径": "Apparel",
        "材质": "Cotton",
        "颜色": "Black",
        "尺码": "M",
        "品牌": "eprolo",
        "item_group_id": "g1",
        "gender": "female",
        "age_group": "adult",
        "identifier_exists": "no",
        "价格": 199.0,
        "_feed_currency": "CNY",
        "库存": 5,
        "图片链接": "https://cdn.example.com/a.jpg",
        "附加图片": "",
        "链接": "https://shop.example.com/products/dress?currency=CNY",
        "合规状态": "pass",
        "违规详情": "0",
    }])
    xml = generate(df, country="US")
    assert "<g:price>199.00 CNY</g:price>" in xml
    assert "USD" not in xml.split("<g:price>")[1].split("</g:price>")[0]


def test_generate_usd_row_no_eur_fx_for_de():
    """DE target must not multiply USD amount by EUR rate when row says USD."""
    df = pd.DataFrame([{
        "SKU": "sku-2",
        "优化后标题": "Test Jacket",
        "标题": "Test Jacket",
        "描述": "Jacket description long enough for feed.",
        "GPC代码": "2271",
        "GPC路径": "Apparel",
        "材质": "Polyester",
        "颜色": "Black",
        "尺码": "L",
        "品牌": "eprolo",
        "item_group_id": "g2",
        "gender": "female",
        "age_group": "adult",
        "identifier_exists": "no",
        "价格": 100.0,
        "_feed_currency": "USD",
        "库存": 3,
        "图片链接": "https://cdn.example.com/b.jpg",
        "附加图片": "",
        "链接": "https://shop.example.com/products/j?currency=USD",
        "合规状态": "pass",
        "违规详情": "0",
    }])
    xml = generate(df, country="DE")
    assert "<g:price>100.00 USD</g:price>" in xml
    # Old FX path would emit ~92 EUR
    assert "92.00 EUR" not in xml
