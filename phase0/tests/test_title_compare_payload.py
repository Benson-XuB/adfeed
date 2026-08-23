from adfeed.feed_quality import build_title_compare_samples


def test_title_compare_samples():
    rows = [{
        "SKU": "1",
        "标题": "2026跨境新款女装法式连衣裙",
        "优化后标题": "eprolo French Vintage Dress for Women - Red, One Size",
    }]
    samples = build_title_compare_samples(rows, limit=5)
    assert samples[0]["before"] == "2026跨境新款女装法式连衣裙"
    assert "French" in samples[0]["after"]
    assert samples[0]["sku"] == "1"


def test_title_compare_skips_identical():
    rows = [
        {"SKU": "same", "标题": "Same Title", "优化后标题": "Same Title"},
        {
            "SKU": "diff",
            "标题": "旧标题",
            "优化后标题": "New Optimized Title",
        },
    ]
    samples = build_title_compare_samples(rows, limit=5)
    assert len(samples) == 1
    assert samples[0]["sku"] == "diff"


def test_title_compare_respects_limit():
    rows = [
        {"SKU": str(i), "标题": f"before-{i}", "优化后标题": f"after-{i}"}
        for i in range(10)
    ]
    samples = build_title_compare_samples(rows, limit=5)
    assert len(samples) == 5
