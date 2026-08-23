"""GMC availability must be binary in_stock / out_of_stock."""
from adfeed.feed_generator import generate as generate_xml


def test_low_inventory_is_in_stock_not_limited():
    """Google Shopping: do not emit limited_availability."""
    rows = [{
        "SKU": "s1",
        "优化后标题": "Tee",
        "描述": "Cotton tee",
        "价格": 19.9,
        "库存": 3,
        "图片链接": "https://cdn.example.com/t.jpg",
        "链接": "https://shop.example.com/products/t?variant=1&currency=USD",
        "品牌": "Demo",
        "颜色": "Black",
        "尺码": "M",
        "_feed_currency": "USD",
    }]
    # generate expects DataFrame-like or list? check signature
    import pandas as pd
    xml = generate_xml(pd.DataFrame(rows), "US", skip_out_of_stock=False)
    assert "limited_availability" not in xml
    assert "<g:availability>in_stock</g:availability>" in xml


def test_zero_inventory_is_out_of_stock():
    import pandas as pd
    rows = [{
        "SKU": "s2",
        "优化后标题": "Tee",
        "描述": "Cotton tee",
        "价格": 19.9,
        "库存": 0,
        "图片链接": "https://cdn.example.com/t.jpg",
        "链接": "https://shop.example.com/products/t?variant=2&currency=USD",
        "品牌": "Demo",
        "_feed_currency": "USD",
    }]
    xml = generate_xml(pd.DataFrame(rows), "US", skip_out_of_stock=False)
    assert "<g:availability>out_of_stock</g:availability>" in xml
    assert "limited_availability" not in xml
