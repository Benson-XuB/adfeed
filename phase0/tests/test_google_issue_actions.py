import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adfeed.google_issue_actions import suggest_action


def test_image_issue_maps_to_feed_image():
    assert suggest_action("image_missing")["action"] == "pick_feed_image"


def test_unknown_maps_to_read_only():
    assert suggest_action("weird_code")["action"] == "view_only"


def test_brand_maps():
    assert suggest_action("missing_brand")["action"] == "confirm_brand"
