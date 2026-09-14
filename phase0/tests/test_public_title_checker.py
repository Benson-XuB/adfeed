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
    </channel></rss>
    """
    r = analyze_feed_titles_bytes(xml, max_items=50)
    assert r["ok"] is True
    assert r["titles_checked"] == 2
    assert r["title_issue_total"] >= 1
    codes = {b["code"] for b in r["buckets"]}
    # Title-only: must not invent brand/image feed buckets
    assert "missing_brand" not in codes
    assert "missing_image" not in codes
    assert "noisy_words" in codes or "noisy_or_long_title" in codes or any(
        c.startswith("missing_") for c in codes
    )
    assert len(r.get("samples") or []) >= 1
