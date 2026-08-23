"""size_system / size_type appear in Google XML when present on the row."""
import pandas as pd

from adfeed.feed_generator import generate


def test_xml_includes_size_system_and_type_when_set():
    df = pd.DataFrame([{
        "SKU": "v1",
        "优化后标题": "eprolo Women Cotton Tee Black M",
        "描述": "Cotton tee",
        "链接": "https://shop.example.com/products/tee?variant=123&currency=USD",
        "图片链接": "https://cdn.example.com/a.jpg",
        "价格": 19.99,
        "_feed_currency": "USD",
        "库存": 3,
        "品牌": "eprolo",
        "颜色": "Black",
        "尺码": "M",
        "size_system": "US",
        "size_type": "Regular",
        "gender": "female",
        "age_group": "adult",
        "identifier_exists": "no",
        "GPC路径": "Apparel > Shirts",
        "GPC代码": "",
        "材质": "Cotton",
        "item_group_id": "p1",
        "合规状态": "pass",
    }])
    xml = generate(df, "US", skip_out_of_stock=False)
    assert "<g:size_system>US</g:size_system>" in xml
    assert "<g:size_type>Regular</g:size_type>" in xml
    assert "<g:size>M</g:size>" in xml
    assert "<g:color>Black</g:color>" in xml
