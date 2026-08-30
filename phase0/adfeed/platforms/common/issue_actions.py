"""Map platform issue codes → in-app actions. Never invent GTIN/brand/color."""

from __future__ import annotations

_RULES: list[tuple[str, str]] = [
    ("image", "pick_feed_image"),
    ("picture", "pick_feed_image"),
    ("photo", "pick_feed_image"),
    ("color", "edit_color_size"),
    ("size", "edit_color_size"),
    ("brand", "confirm_brand"),
    ("identifier", "view_only"),
    ("gtin", "view_only"),
]


def suggest_action(reason_code: str) -> dict:
    code = (reason_code or "").strip().lower()
    for needle, action in _RULES:
        if needle in code:
            return {"action": action, "reason_code": reason_code or ""}
    return {"action": "view_only", "reason_code": reason_code or ""}
