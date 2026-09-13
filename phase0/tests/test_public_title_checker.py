from adfeed.public_tools.title_checker import analyze_title


def test_noisy_long_title_flags_improve():
    r = analyze_title("Women's Summer Dress Casual Loose New Arrival Free Shipping Hot Sale")
    assert r["ok"] is True
    assert r["verdict"] in ("improve", "ok", "weak")
    codes = {i["code"] for i in r["issues"]}
    assert "noisy_words" in codes or "too_long" in codes


def test_short_clean_title_ok_or_soft_gaps():
    r = analyze_title("Women's Linen Midi Dress Blue M")
    assert r["ok"] is True
    assert "suggested_title" in r  # may equal input if already fine
