import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_google_export_writes_item(tmp_path):
    from adfeed.platforms.common.registry import get_platform
    import adfeed.platforms  # noqa: F401

    out = tmp_path / "google" / "us.xml"
    n = get_platform("google").export_feed(
        [
            {
                "SKU": "SKU-1",
                "优化后标题": "Red Dress M",
                "描述": "A dress",
                "链接": "https://example.com/p/sku-1",
                "图片链接": "https://example.com/i.jpg",
                "价格": 29.0,
                "_feed_currency": "USD",
                "库存": 2,
                "品牌": "Brand",
                "GPC代码": "4174",
                "颜色": "Red",
                "尺码": "M",
            }
        ],
        output_path=out,
        country="US",
    )
    assert n >= 1
    text = out.read_text(encoding="utf-8")
    assert "SKU-1" in text
