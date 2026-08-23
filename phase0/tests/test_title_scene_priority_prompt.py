"""Title prompt: world apparel formula; scene optional (有则加)."""
from adfeed.title_optimizer import (
    _FEED_TITLE_PREMISE,
    _PROMPT_DE,
    _PROMPT_EN,
    _PROMPT_ES,
    _PROMPT_FR,
    _PROMPT_IT,
)


def test_en_prompt_scene_is_optional_not_number_one():
    assert "Scene words are the #1 priority" not in _PROMPT_EN
    assert "SCENE is optional" in _PROMPT_EN or "scene is optional" in _PROMPT_EN.lower()
    assert "CORE CATEGORY" in _PROMPT_EN or "product type" in _PROMPT_EN.lower()
    low = _PROMPT_EN.lower()
    assert "drop scene first" in low


def test_en_premise_world_formula():
    p = _FEED_TITLE_PREMISE.lower()
    assert "≤2" in _FEED_TITLE_PREMISE or "at most 2" in p or "max 2" in p
    assert "closure" in p
    assert "pattern" in p or "floral" in p
    assert "polyester" in p


def test_en_prompt_bans_closure_and_prefers_pattern_slot():
    low = _PROMPT_EN.lower()
    assert "pullover closure" in low or "closure" in low
    assert "fitted fit" in low or "fit type" in low
    assert "floral" in low or "pattern" in low


def test_other_locale_prompts_mark_scene_optional():
    assert "Szene optional" in _PROMPT_DE
    assert "PRIORITÄT #1" not in _PROMPT_DE
    assert "Scène optionnelle" in _PROMPT_FR or "scène optionnelle" in _PROMPT_FR
    assert "Escena opcional" in _PROMPT_ES
    assert "Scena opzionale" in _PROMPT_IT
