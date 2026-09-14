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
    tip_codes = {i["code"] for i in r["tips"]}
    assert "missing_size" in tip_codes
    # Soft tip must not force improve (we refuse to invent a size).
    assert r["verdict"] == "ok"
    assert "missing_size" not in {i["code"] for i in r["issues"]}


def test_non_apparel_clean_title_not_flagged_for_missing_attrs():
    r = analyze_title("kakaku Business Card Case for Professionals, Multicolor")
    assert r["verdict"] == "ok"
    assert r["issues"] == []
    assert r["tips"] == []
    assert r["suggestion_changed"] is False


def test_apparel_soft_tips_do_not_force_improve():
    r = analyze_title("Women's Cotton Dress Blue")
    assert r["verdict"] == "ok"
    tip_codes = {t["code"] for t in r["tips"]}
    assert "missing_style" in tip_codes or "missing_size" in tip_codes
    assert all(i["code"] in {"too_long", "noisy_words"} for i in r["issues"])


def test_filter_ai_title_rejects_invented_tokens():
    from adfeed.public_tools.title_checker import filter_ai_title

    src = "Women's Cotton Dress Blue"
    out = filter_ai_title(src, "Nike Women's Silk Dress Blue")
    assert "Nike" not in out
    assert "Silk" not in out
    assert "Dress" in out
    assert "Blue" in out


def test_suggest_title_ai_falls_back_without_key(monkeypatch):
    from adfeed.public_tools import title_checker as tc

    monkeypatch.setattr(tc, "_llm_available", lambda: False)
    r = tc.suggest_title_ai("Women's Dress Free Shipping Hot Sale")
    assert r["ok"] is True
    assert r["source"] == "rules"
    assert "Free Shipping" not in r["suggested_title"]


def test_suggest_title_ai_uses_llm_when_available(monkeypatch):
    from adfeed.public_tools import title_checker as tc

    monkeypatch.setattr(tc, "_llm_available", lambda: True)

    def fake_llm(title: str) -> str:
        return "Women's Summer Dress Casual Loose"

    monkeypatch.setattr(tc, "_llm_suggest_title", fake_llm)
    raw = "Women's Summer Dress Casual Loose New Arrival Free Shipping"
    r = tc.suggest_title_ai(raw)
    assert r["ok"] is True
    assert r["source"] == "ai"
    assert r["suggested_title_ai"] == "Women's Summer Dress Casual Loose"
    assert "Free Shipping" not in r["suggested_title_ai"]


def test_analyze_feed_titles_bytes_counts_title_issues_only():
    from adfeed.public_tools.title_checker import analyze_feed_titles_bytes

    xml = b"""<?xml version="1.0"?>
    <rss xmlns:g="http://base.google.com/ns/1.0"><channel>
      <item>
        <g:id>1</g:id>
        <g:title>Dress Free Shipping Hot Sale</g:title>
        <g:brand></g:brand>
        <g:image_link></g:image_link>
      </item>
      <item>
        <g:id>2</g:id>
        <g:title>Women's Linen Midi Dress Blue M</g:title>
      </item>
      <item>
        <g:id>3</g:id>
        <g:title>kakaku Business Card Case for Professionals, Multicolor</g:title>
      </item>
    </channel></rss>
    """
    r = analyze_feed_titles_bytes(xml, max_items=50)
    assert r["ok"] is True
    assert r["titles_checked"] == 3
    assert r["titles_with_issues"] == 1  # only noisy dress
    codes = {b["code"] for b in r["buckets"]}
    assert "missing_brand" not in codes
    assert "missing_image" not in codes
    assert "noisy_words" in codes
    assert "missing_audience" not in codes  # soft tips are not hard buckets
    tip_codes = {b["code"] for b in r.get("tip_buckets") or []}
    assert "missing_audience" in tip_codes or "missing_material" in tip_codes
    assert len(r.get("samples") or []) >= 1
