"""Style-axis title skeletons — searchable diffs, never Style N."""
from adfeed.style_axis_title import (
    apply_style_skeleton,
    collect_style_axis_profiles,
    infer_style_title_skeletons,
)


def test_collect_profiles_groups_opaque_styles():
    variants = [
        {"color": "Style 1", "size": "S", "image_url": "https://cdn.example/a.jpg"},
        {"color": "Style 1", "size": "L", "image_url": "https://cdn.example/a.jpg"},
        {"color": "Style 2", "size": "S", "image_url": "https://cdn.example/b.jpg"},
        {"color": "Black", "size": "M", "image_url": "https://cdn.example/c.jpg"},
    ]
    profiles = collect_style_axis_profiles(variants, title="Jacket", description="Color: brown")
    assert set(profiles) == {"style-1", "style-2"}
    assert profiles["style-1"]["image_url"].endswith("a.jpg")
    assert profiles["style-2"]["image_url"].endswith("b.jpg")
    assert "Black" not in str(profiles)


def test_apply_style_skeleton_rejects_style_codes():
    base = "Women's V-Neck Jacket"
    assert apply_style_skeleton(base, "Women's Lace-Up Belted Jacket") == "Women's Lace-Up Belted Jacket"
    assert apply_style_skeleton(base, "Women's Style 1 Jacket") == base
    assert apply_style_skeleton(base, "") == base


def test_infer_uses_llm_fn_and_rejects_codes():
    profiles = {
        "style-1": {"raw": "Style 1", "image_url": "https://x/a.jpg", "sizes": ["S"]},
        "style-2": {"raw": "Style 2", "image_url": "https://x/b.jpg", "sizes": ["S"]},
    }

    def fake_llm(**kwargs):
        return {
            "style-1": "Women's Lace-Up Belted V-Neck Jacket",
            "style-2": "Women's Style 2 Zip Jacket",  # banned — dropped
        }

    out = infer_style_title_skeletons(
        product_title="Jacket",
        description="Color: brown",
        profiles=profiles,
        base_skeleton="Women's V-Neck Jacket",
        llm_fn=fake_llm,
    )
    assert out["style-1"] == "Women's Lace-Up Belted V-Neck Jacket"
    assert "style-2" not in out  # rejected Style 2 in text


def test_style_skeleton_wins_over_shared_asset_title():
    """Platform product assets are shared — must not flatten Style 1 vs Style 2 titles."""
    asset = "Women's V-Neck Long Sleeve Jacket Casual"
    sk1 = "Women's Lace-Up Belted PU Leather Jacket"
    sk2 = "Women's Zip Front Bomber PU Leather Jacket"
    assert apply_style_skeleton(asset, sk1) == sk1
    assert apply_style_skeleton(asset, sk2) == sk2
    assert apply_style_skeleton(asset, sk1) != apply_style_skeleton(asset, sk2)
