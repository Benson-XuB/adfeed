from adfeed.public_tools.title_checker import analyze_title


def test_noisy_long_title_flags_improve():
    raw = "Women's Summer Dress Casual Loose New Arrival Free Shipping Hot Sale"
    r = analyze_title(raw)
    assert r["ok"] is True
    assert r["verdict"] == "improve"
    codes = {i["code"] for i in r["issues"]}
    assert "noisy_words" in codes
    assert "Free Shipping" not in r["suggested_title"]
    assert len(r["suggested_title"]) < len(raw)


def test_short_clean_title_ok_or_soft_gaps():
    r = analyze_title("Women's Linen Midi Dress Blue M")
    assert r["ok"] is True
    assert r["verdict"] == "ok"
    assert r["suggested_title"] == "Women's Linen Midi Dress Blue M"
    assert r["present"]["audience"] is True
    assert r["present"]["material"] is True
    assert r["present"]["style"] is True
    assert r["present"]["color"] is True
    assert r["present"]["size"] is True


def test_pack_quantity_not_treated_as_size():
    r = analyze_title("Pack of 2 Cotton Socks Black")
    assert r["ok"] is True
    assert r["present"]["size"] is False
    codes = {i["code"] for i in r["issues"]}
    assert "missing_size" in codes
