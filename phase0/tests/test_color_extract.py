"""S1b: LLM/dict color extract from title+description."""
from adfeed.color_extract import extract_color_from_text


def test_extract_returns_black_from_chinese(monkeypatch):
    def fake_llm(prompt):
        return "Black"

    monkeypatch.setattr("adfeed.color_extract._llm_color", fake_llm)
    assert extract_color_from_text("法式连衣裙 黑色 V领", "") == "Black"


def test_extract_multicolor_when_none(monkeypatch):
    monkeypatch.setattr("adfeed.color_extract._llm_color", lambda p: "Multicolor")
    assert extract_color_from_text("USB cable 2m", "") == "Multicolor"
