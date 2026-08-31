import csv
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_tiktok_feed_does_not_invent_weight():
    from adfeed.platforms.tiktok.feed import generate_tiktok_feed

    csv_text = generate_tiktok_feed(
        [
            {
                "SKU": "SKU-1",
                "item_group_id": "P1",
                "优化后标题": "Test Dress",
                "描述": "desc",
                "品牌": "Brand",
                "GPC代码": "4174",
                "GPC路径": "Apparel & Accessories > Clothing > Dresses",
                "图片链接": "https://example.com/a.jpg",
                "价格": 19.99,
                "库存": 3,
                "颜色": "Red",
                "尺码": "M",
            }
        ]
    )
    reader = csv.DictReader(io.StringIO(csv_text))
    row = next(reader)
    assert row["Weight (kg)"] == ""
    assert row["Package Length (cm)"] == ""
    assert row["Package Width (cm)"] == ""
    assert row["Package Height (cm)"] == ""


def test_tiktok_feed_passes_through_real_weight():
    from adfeed.platforms.tiktok.feed import generate_tiktok_feed

    csv_text = generate_tiktok_feed(
        [
            {
                "SKU": "SKU-1",
                "item_group_id": "P1",
                "优化后标题": "Test",
                "描述": "d",
                "价格": 10,
                "库存": 1,
                "weight_kg": 0.45,
            }
        ]
    )
    row = next(csv.DictReader(io.StringIO(csv_text)))
    assert row["Weight (kg)"] == "0.45"


def test_meta_export_writes_items(tmp_path):
    from adfeed.platforms.common.registry import get_platform

    out = tmp_path / "meta" / "us.xml"
    n = get_platform("meta").export_feed(
        [
            {
                "SKU": "SKU-1",
                "优化后标题": "Title",
                "描述": "Desc",
                "链接": "https://example.com/p",
                "图片链接": "https://example.com/i.jpg",
                "价格": 12.5,
                "_feed_currency": "USD",
                "库存": 2,
                "品牌": "B",
            }
        ],
        output_path=out,
        country="US",
        shop_name="Shop",
        site_link="https://example.com",
    )
    assert n == 1
    assert out.exists()
    assert "<id>SKU-1</id>" in out.read_text(encoding="utf-8")


def test_tiktok_category_prefers_gpc_path_over_misleading_code():
    """AdFeed aliases (e.g. jacket→5598) disagree with official GPC; path wins."""
    from adfeed.platforms.tiktok.feed import _gpc_to_tiktok_category

    assert (
        _gpc_to_tiktok_category(
            "5598",
            "Apparel & Accessories > Clothing > Outerwear > Coats & Jackets",
        )
        == "Women's Clothing > Jackets & Coats"
    )
    assert (
        _gpc_to_tiktok_category(
            "2271",
            "Apparel & Accessories > Clothing > Dresses",
        )
        == "Women's Clothing > Dresses"
    )
    assert (
        _gpc_to_tiktok_category(
            "209",
            "Apparel & Accessories > Clothing > Underwear & Socks > Socks",
        )
        == "Socks & Hosiery"
    )
    assert (
        _gpc_to_tiktok_category(
            "204",
            "Apparel & Accessories > Clothing > Pants",
        )
        == "Women's Clothing > Pants"
    )


def test_tiktok_feed_category_column_uses_path():
    from adfeed.platforms.tiktok.feed import generate_tiktok_feed

    csv_text = generate_tiktok_feed(
        [
            {
                "SKU": "J1",
                "item_group_id": "P-J",
                "优化后标题": "Women Jacket",
                "描述": "d",
                "品牌": "Northvale",
                "GPC代码": "5598",
                "GPC路径": "Apparel & Accessories > Clothing > Outerwear > Coats & Jackets",
                "图片链接": "https://example.com/j.jpg",
                "价格": 30,
                "库存": 1,
            }
        ]
    )
    row = next(csv.DictReader(io.StringIO(csv_text)))
    assert row["Category"] == "Women's Clothing > Jackets & Coats"


def test_tiktok_jeans_title_with_pants_gpc_maps_to_jeans():
    """Google has no Jeans leaf (204=Pants); TikTok still gets Jeans from title."""
    from adfeed.platforms.tiktok.feed import _gpc_to_tiktok_category, generate_tiktok_feed

    assert (
        _gpc_to_tiktok_category(
            "204",
            "Apparel & Accessories > Clothing > Pants",
            title="Northvale Women's High Waist Denim Jeans, Blue, Size M",
        )
        == "Women's Clothing > Jeans"
    )
    assert (
        _gpc_to_tiktok_category(
            "204",
            "Apparel & Accessories > Clothing > Pants",
            title="Women's Wide Leg Trousers Black",
        )
        == "Women's Clothing > Pants"
    )

    csv_text = generate_tiktok_feed(
        [
            {
                "SKU": "JN1",
                "item_group_id": "P-JN",
                "优化后标题": "Northvale Women's High Waist Denim Jeans, Blue, Size M",
                "描述": "d",
                "品牌": "Northvale",
                "GPC代码": "204",
                "GPC路径": "Apparel & Accessories > Clothing > Pants",
                "图片链接": "https://example.com/jn.jpg",
                "价格": 44.52,
                "库存": 2,
            }
        ]
    )
    row = next(csv.DictReader(io.StringIO(csv_text)))
    assert row["Category"] == "Women's Clothing > Jeans"
