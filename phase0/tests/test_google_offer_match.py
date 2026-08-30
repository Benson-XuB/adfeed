import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adfeed.google_offer_match import match_offer_to_sku


def test_exact_sku_match():
    assert match_offer_to_sku("RED-M", {"RED-M", "BLUE-S"}) == "RED-M"


def test_unmatched_returns_none():
    assert match_offer_to_sku("UNKNOWN", {"RED-M"}) is None


def test_no_fuzzy_steal():
    assert match_offer_to_sku("SKU-RED", {"RED"}) is None
