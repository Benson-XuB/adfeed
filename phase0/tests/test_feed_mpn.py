"""Do not mint fake MPNs when walking the no-GTIN identifier path."""
import pandas as pd
from adfeed.feed_generator import generate as generate_xml


def _row(**extra):
    base = {
        "SKU": "A8842A68B5FF40CB8B382327EEEF6C40",
        "优化后标题": "Women Dress Black L",
        "描述": "Cotton dress",
        "价格": 19.9,
        "库存": 3,
        "图片链接": "https://cdn.example.com/t.jpg",
        "链接": "https://shop.example.com/products/t?variant=1&currency=USD",
        "品牌": "eprolo",
        "颜色": "Black",
        "尺码": "L",
        "identifier_exists": "no",
        "gtin": "",
        "_feed_currency": "USD",
    }
    base.update(extra)
    return base


def test_no_gtin_omits_mpn_instead_of_copying_sku():
    xml = generate_xml(pd.DataFrame([_row()]), "US")
    assert "<g:identifier_exists>no</g:identifier_exists>" in xml
    assert "<g:mpn>" not in xml
    assert "A8842A68B5FF40CB8B382327EEEF6C40" in xml  # still the offer id
    assert "<g:brand>eprolo</g:brand>" in xml


def test_xml_gender_follows_women_in_final_title():
    xml = generate_xml(pd.DataFrame([_row(
        **{"优化后标题": "Women Jacket PU Slim Fit", "gender": "unisex"}
    )]), "US")
    assert "<g:gender>female</g:gender>" in xml
    assert "<g:gender>unisex</g:gender>" not in xml
