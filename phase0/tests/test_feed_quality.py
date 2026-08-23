"""Feed quality gate: One Size autofix + report levels."""
from adfeed.feed_quality import (
    QualityEvent,
    QualityReport,
    apply_row_autofixes,
    is_apparel_like,
    process_feed_rows,
    traffic_light,
)


def test_traffic_light_red_on_fatal():
    r = QualityReport(fatals=[QualityEvent("FATAL", "I01", "g:image_link", "x", "no image")])
    assert traffic_light(r) == "red"


def test_traffic_light_yellow_on_autofix_only():
    r = QualityReport(autofixed=[QualityEvent("AUTOFIX", "S01", "g:size", "x", "One Size")])
    assert traffic_light(r) == "yellow"


def test_traffic_light_green_when_clean():
    assert traffic_light(QualityReport(total_rows=1)) == "green"


def test_to_dict_includes_light_and_before_after():
    ev = QualityEvent("AUTOFIX", "S01", "g:size", "sku1", "filled",
                      suggestion="", before="", after="One Size")
    d = QualityReport(autofixed=[ev], total_rows=1).to_dict()
    assert d["light"] == "yellow"
    assert d["autofixed"][0]["after"] == "One Size"



def test_socks_title_is_apparel_like():
    assert is_apparel_like(title="eprolo Women Boat Socks Black")
    assert is_apparel_like(gpc_path="Apparel & Accessories > Clothing > Socks")


def test_electronics_not_forced_apparel():
    assert not is_apparel_like(title="USB-C Charging Cable 2m", gpc_path="Electronics > Communications")


def test_one_size_autofix_for_socks():
    row = {
        "SKU": "sock-1",
        "优化后标题": "eprolo Women Boat Socks Black",
        "GPC路径": "Apparel & Accessories > Clothing > Socks",
        "尺码": "",
        "颜色": "Black",
        "价格": 9.9,
        "图片链接": "https://cdn.example.com/a.jpg",
        "链接": "https://shop.example.com/products/socks",
    }
    events = apply_row_autofixes(row)
    assert row["尺码"] == "One Size"
    assert any(e.rule_id == "S01" for e in events)


def test_process_rows_keeps_fatal_but_reports():
    rows = [{
        "SKU": "bad-1",
        "优化后标题": "Nice Dress",
        "GPC路径": "Apparel > Dresses",
        "尺码": "M",
        "颜色": "Red",
        "价格": 10,
        "图片链接": "",  # fatal
        "链接": "https://shop.example.com/products/d",
    }]
    report = process_feed_rows(rows)
    assert rows[0]["尺码"] == "M"
    assert any(e.rule_id == "I01" for e in report.fatals)
    # row still present for feed write
    assert len(rows) == 1


def test_process_socks_autofix_in_report():
    rows = [{
        "SKU": "sock-2",
        "优化后标题": "Boat Socks White",
        "GPC路径": "Apparel > Socks",
        "尺码": "",
        "颜色": "White",
        "价格": 8,
        "图片链接": "https://cdn.example.com/b.jpg",
        "链接": "https://shop.example.com/products/s",
    }]
    report = process_feed_rows(rows)
    assert rows[0]["尺码"] == "One Size"
    assert report.to_dict()["summary"]["autofixed"] >= 1


def test_condition_default_new():
    row = {"SKU": "a", "优化后标题": "Cotton Tee", "GPC路径": "Apparel > Shirts",
           "尺码": "M", "颜色": "Black", "价格": 10,
           "图片链接": "https://x/a.jpg", "链接": "https://s.com/p/a"}
    apply_row_autofixes(row)
    assert row.get("condition") == "new"


def test_gender_default_unisex_apparel():
    row = {"SKU": "a", "优化后标题": "Cotton Tee", "GPC路径": "Apparel > Shirts",
           "尺码": "M", "颜色": "Black"}
    apply_row_autofixes(row)
    assert row.get("gender") in ("unisex", "female", "male")


def test_osfa_aliases_normalize_to_one_size():
    row = {"SKU": "a", "优化后标题": "Socks", "GPC路径": "Apparel > Socks", "尺码": "OSFA"}
    events = apply_row_autofixes(row)
    assert row["尺码"] == "One Size"
    assert any(e.rule_id == "S05" for e in events)


def test_one_size_already_canonical_does_not_renag_s05():
    row = {
        "SKU": "a",
        "优化后标题": "Pure Cotton Boat Socks",
        "GPC路径": "Apparel > Socks",
        "尺码": "One Size",
    }
    events = apply_row_autofixes(row)
    assert row["尺码"] == "One Size"
    assert not any(e.rule_id == "S05" for e in events)
    assert not any(e.rule_id == "S01" for e in events)


def test_no_gtin_sets_identifier_exists_false():
    row = {
        "SKU": "a", "优化后标题": "Widget", "GPC路径": "Hardware",
        "价格": 5, "图片链接": "https://x/a.jpg", "链接": "https://s.com/p/a",
        "gtin": "", "identifier_exists": "",
        "brand": "",
    }
    events = apply_row_autofixes(row, brand_fallback="My Store")
    assert str(row.get("identifier_exists")).lower() in ("false", "no")
    assert row.get("brand") == "My Store"
    assert any(e.rule_id == "ID01" for e in events)
    id01 = next(e for e in events if e.rule_id == "ID01")
    assert "identifier" in id01.message.lower() or "barcode" in id01.message.lower() or "no-barcode" in id01.message.lower()


def test_unisex_gender_realigns_when_title_says_women():
    row = {
        "SKU": "g1",
        "优化后标题": "eprolo Women High Waist Jeans Blue",
        "GPC路径": "Apparel & Accessories > Clothing > Pants",
        "尺码": "M",
        "颜色": "Blue",
        "gender": "unisex",
        "价格": 19.9,
        "图片链接": "https://cdn.example.com/a.jpg",
        "链接": "https://shop.example.com/products/a",
    }
    events = apply_row_autofixes(row)
    assert row["gender"] == "female"
    assert any(e.rule_id == "S04" for e in events)



def test_id02_myshopify_brand_replaced_with_fallback():
    row = {
        "SKU": "a", "优化后标题": "Widget", "GPC路径": "Hardware",
        "价格": 5, "图片链接": "https://x/a.jpg", "链接": "https://s.com/p/a",
        "gtin": "", "identifier_exists": "no",
        "brand": "cool-shop.myshopify.com",
    }
    events = apply_row_autofixes(row, brand_fallback="My Store")
    assert row.get("brand") == "My Store"
    id02 = next(e for e in events if e.rule_id == "ID02")
    assert id02.level == "AUTOFIX"
    assert id02.after == "My Store"
    assert "myshopify" in id02.before.lower()


def test_id02_myshopify_brand_warns_without_fallback():
    row = {
        "SKU": "a", "优化后标题": "Widget", "GPC路径": "Hardware",
        "价格": 5, "图片链接": "https://x/a.jpg", "链接": "https://s.com/p/a",
        "gtin": "", "identifier_exists": "no",
        "brand": "cool-shop.myshopify.com",
    }
    events = apply_row_autofixes(row, brand_fallback="")
    assert row.get("brand") == "cool-shop.myshopify.com"
    id02 = next(e for e in events if e.rule_id == "ID02")
    assert id02.level == "WARN"


def test_apparel_empty_color_gets_multicolor_autofix(monkeypatch):
    monkeypatch.setattr(
        "adfeed.color_extract.extract_color_from_text",
        lambda t, d: "Multicolor",
    )
    row = {
        "SKU": "d1", "优化后标题": "Summer Dress", "描述": "法式碎花裙",
        "GPC路径": "Apparel > Dresses", "尺码": "M", "颜色": "",
        "价格": 20, "图片链接": "https://x/a.jpg", "链接": "https://s.com/p/d",
    }
    from adfeed.feed_quality import enrich_and_autofix_row
    events = enrich_and_autofix_row(row)
    assert row["颜色"] == "Multicolor"
    assert any(e.rule_id == "C01" for e in events)


def test_apparel_existing_color_not_overwritten_by_multicolor(monkeypatch):
    monkeypatch.setattr(
        "adfeed.color_extract.extract_color_from_text",
        lambda t, d: "Multicolor",
    )
    row = {
        "SKU": "d2", "优化后标题": "Summer Dress", "描述": "法式碎花裙",
        "GPC路径": "Apparel > Dresses", "尺码": "M", "颜色": "Black",
        "价格": 20, "图片链接": "https://x/a.jpg", "链接": "https://s.com/p/d",
    }
    from adfeed.feed_quality import enrich_and_autofix_row
    events = enrich_and_autofix_row(row)
    assert row["颜色"] == "Black"
    assert not any(e.rule_id in ("C01", "C02") for e in events)
