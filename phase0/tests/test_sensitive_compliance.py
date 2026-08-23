"""S6a: sensitive lexicon soften + adult=yes (P0 tiers)."""
from adfeed.sensitive_compliance import apply_sensitive_compliance, LP_SYNC_HINT
from adfeed.feed_quality import process_feed_rows


def test_soften_tactical_knife():
    row = {
        "SKU": "k1",
        "优化后标题": "Tactical Combat Knife for Self Defense",
        "描述": "tactical combat knife",
    }
    events = apply_sensitive_compliance(row)
    title = row["优化后标题"].lower()
    assert "combat" not in title
    assert "camping" in title or "outdoor" in title or "tool" in title
    assert any(e.rule_id.startswith("SEN") for e in events)
    # SOFT tier: no adult
    assert str(row.get("adult") or "no").lower() not in ("yes", "true")


def test_lingerie_forces_adult():
    row = {
        "SKU": "u1",
        "优化后标题": "Sexy Lace Lingerie Set for Women",
        "描述": "sexy lingerie",
        "GPC路径": "Apparel > Underwear",
    }
    events = apply_sensitive_compliance(row)
    assert str(row.get("adult")).lower() in ("yes", "true")
    assert any(e.rule_id == "AD01" for e in events)


def test_plain_underwear_does_not_force_adult():
    """P0: everyday underwear / shapewear must not auto adult=yes."""
    row = {
        "SKU": "u2",
        "优化后标题": "Women's Cotton Underwear Briefs 3-Pack",
        "描述": "everyday cotton underwear for daily wear",
        "GPC路径": "Apparel & Accessories > Clothing > Underwear",
    }
    events = apply_sensitive_compliance(row)
    assert str(row.get("adult") or "no").lower() not in ("yes", "true")
    assert not any(e.rule_id == "AD01" for e in events)


def test_shapewear_without_sexy_does_not_force_adult():
    row = {
        "SKU": "u3",
        "优化后标题": "Women Shapewear Tummy Control Bodysuit",
        "描述": "shapewear underwear for waist training",
        "GPC路径": "Apparel & Accessories > Clothing > Underwear",
    }
    apply_sensitive_compliance(row)
    assert str(row.get("adult") or "no").lower() not in ("yes", "true")


def test_block_tier_emits_fatal():
    row = {
        "SKU": "b1",
        "优化后标题": "Military Switchblade Knife",
        "描述": "switchblade for sale",
    }
    events = apply_sensitive_compliance(row)
    assert any(
        e.level == "FATAL" and e.rule_id.startswith("SEN")
        for e in events
    )


def test_soften_includes_landing_page_sync_suggestion():
    row = {
        "SKU": "k4",
        "优化后标题": "Tactical Combat Knife",
        "描述": "tactical combat knife",
    }
    events = apply_sensitive_compliance(row)
    assert any(LP_SYNC_HINT in (e.suggestion or "") for e in events)


def test_adult_event_includes_landing_page_sync_suggestion():
    row = {
        "SKU": "u4",
        "优化后标题": "Sexy Lace Lingerie Set",
        "描述": "lingerie",
    }
    events = apply_sensitive_compliance(row)
    ad01 = [e for e in events if e.rule_id == "AD01"]
    assert ad01
    assert LP_SYNC_HINT in (ad01[0].suggestion or "")


def test_massage_gun_softens_adult_leaning_phrase():
    row = {
        "SKU": "m1",
        "优化后标题": "Deep Tissue Adult Massage Gun for Couples",
        "描述": "intimate massage gun for bedroom pleasure",
    }
    events = apply_sensitive_compliance(row)
    blob = f"{row['优化后标题']} {row['描述']}".lower()
    assert "pleasure" not in blob
    assert "intimate" not in blob or "muscle" in blob or "recovery" in blob
    assert any(e.rule_id.startswith("SEN") for e in events)


def test_process_feed_rows_includes_sensitive_events():
    rows = [{
        "SKU": "k2",
        "优化后标题": "Tactical Combat Knife",
        "描述": "tactical combat knife for camping",
        "价格": 19.9,
        "图片链接": "https://cdn.example.com/k.jpg",
        "链接": "https://shop.example.com/products/k",
    }]
    report = process_feed_rows(rows)
    assert "combat" not in rows[0]["优化后标题"].lower()
    assert any(e.rule_id.startswith("SEN") for e in report.autofixed + report.warnings)


def test_apply_after_asset_title_overwrite_softens():
    """Pipeline merges asset.title after quality gate; must re-soften for Feed."""
    row = {
        "SKU": "k3",
        "优化后标题": "Outdoor Camping Tool",
        "描述": "camping tool",
    }
    row["优化后标题"] = "Tactical Combat Knife for Self Defense"
    apply_sensitive_compliance(row)
    title = row["优化后标题"].lower()
    assert "combat" not in title
    assert "camping" in title or "outdoor" in title or "tool" in title


def test_p1_erotic_forces_adult():
    row = {
        "SKU": "u5",
        "优化后标题": "Erotic Lace Bodysuit for Women",
        "描述": "erotic nightwear",
    }
    events = apply_sensitive_compliance(row)
    assert str(row.get("adult")).lower() in ("yes", "true")
    assert any(e.rule_id == "AD01" for e in events)


def test_p1_massage_gun_chinese_couples_softens():
    row = {
        "SKU": "m2",
        "优化后标题": "专业筋膜枪 情侣专用",
        "描述": "筋膜枪适合情侣放松",
        "GPC路径": "Health > Massage",
    }
    events = apply_sensitive_compliance(row)
    blob = f"{row['优化后标题']} {row['描述']}"
    assert "情侣" not in blob
    assert any(e.rule_id.startswith("SEN") for e in events)
    assert str(row.get("adult") or "no").lower() not in ("yes", "true")


def test_p1_butterfly_knife_is_block():
    row = {
        "SKU": "b2",
        "优化后标题": "Carbon Steel Butterfly Knife",
        "描述": "balisong butterfly knife",
    }
    events = apply_sensitive_compliance(row)
    assert any(e.level == "FATAL" and e.rule_id.startswith("SEN") for e in events)


def test_p1_fangshen_dao_softens():
    row = {
        "SKU": "k5",
        "优化后标题": "户外防身刀锋利耐用",
        "描述": "防身刀便携",
    }
    events = apply_sensitive_compliance(row)
    title = row["优化后标题"]
    assert "防身刀" not in title
    assert any(e.rule_id.startswith("SEN") for e in events)
    assert str(row.get("adult") or "no").lower() not in ("yes", "true")
