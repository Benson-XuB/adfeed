"""Material WARN + English description hardening in feed_quality."""
from adfeed.feed_quality import apply_row_autofixes, process_feed_rows
from adfeed.desc_formatter import prepare_feed_description, cjk_ratio


def test_translate_chinese_material_autofix():
    row = {
        "SKU": "m1",
        "优化后标题": "Women Dress",
        "GPC路径": "Apparel & Accessories > Clothing > Dresses",
        "材质": "聚酯纤维",
        "描述": "Nice dress",
        "价格": 19.9,
        "图片链接": "https://cdn.example.com/a.jpg",
        "链接": "https://shop.example.com/products/a",
    }
    events = apply_row_autofixes(row)
    assert "聚酯" not in str(row.get("材质"))
    assert "Polyester" in str(row.get("材质"))
    assert any(e.rule_id == "M01" for e in events)


def test_apparel_missing_material_warn_or_infer():
    row = {
        "SKU": "m2",
        "优化后标题": "Women Summer Dress Floral",
        "GPC路径": "Apparel & Accessories > Clothing > Dresses",
        "材质": "",
        "描述": "Floral dress",
        "价格": 19.9,
        "图片链接": "https://cdn.example.com/a.jpg",
        "链接": "https://shop.example.com/products/a",
    }
    events = apply_row_autofixes(row)
    # Either inferred from title keywords or WARN M02
    assert row.get("材质") or any(e.rule_id == "M02" for e in events)
    if not row.get("材质"):
        assert any(e.rule_id == "M02" and e.level == "WARN" for e in events)


def test_title_keyword_infers_cotton():
    row = {
        "SKU": "m3",
        "优化后标题": "100% Cotton Tee for Men",
        "GPC路径": "Apparel & Accessories > Clothing > Shirts & Tops",
        "材质": "",
        "描述": "Soft tee",
        "价格": 12,
        "图片链接": "https://cdn.example.com/a.jpg",
        "链接": "https://shop.example.com/products/a",
    }
    events = apply_row_autofixes(row)
    assert "Cotton" in str(row.get("材质"))
    assert any(e.rule_id == "M03" for e in events)


def test_prepare_translates_chinese_labels():
    raw = "颜色:蓝色面料:纯棉风格:休闲"
    out, meta = prepare_feed_description(raw)
    assert "Color:" in out or "color:" in out.lower()
    assert "蓝色" in out or "Blue" in out or "Cotton" in out or "面料" not in out or "Fabric" in out
    assert meta.get("changed")


def test_heavy_cjk_description_replaced_with_en_summary():
    row = {
        "SKU": "d1",
        "优化后标题": "Women Casual Dress",
        "GPC路径": "Apparel & Accessories > Clothing > Dresses",
        "材质": "Polyester",
        "颜色": "Blue",
        "描述": "这是一款非常漂亮的连衣裙适合夏季穿着面料舒适透气版型修身显瘦百搭",
        "价格": 29,
        "图片链接": "https://cdn.example.com/a.jpg",
        "链接": "https://shop.example.com/products/a",
    }
    events = apply_row_autofixes(row)
    desc = str(row.get("描述") or "")
    assert cjk_ratio(desc) < 0.2
    assert any(e.rule_id in ("D01", "D03") for e in events)


def test_process_feed_rows_emits_material_or_desc_events():
    rows = [{
        "SKU": "x1",
        "优化后标题": "Cotton Blouse",
        "GPC路径": "Apparel & Accessories > Clothing > Shirts & Tops",
        "材质": "棉",
        "描述": "Soft blouse",
        "价格": 15,
        "图片链接": "https://cdn.example.com/a.jpg",
        "链接": "https://shop.example.com/products/a",
    }]
    report = process_feed_rows(rows)
    assert "棉" not in str(rows[0].get("材质"))
    assert any(
        e.rule_id.startswith("M")
        for e in report.autofixed + report.warnings
    )
