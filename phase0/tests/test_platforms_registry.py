"""Registry must expose google/meta/tiktok platform modules."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_registry_lists_google_meta_tiktok():
    from adfeed.platforms.common.registry import list_platform_ids

    assert set(list_platform_ids()) >= {"google", "meta", "tiktok"}


def test_get_exporter_google():
    from adfeed.platforms.common.registry import get_platform

    p = get_platform("google")
    assert hasattr(p, "export_feed")
    assert callable(p.export_feed)


def test_get_platform_unknown_raises():
    from adfeed.platforms.common.registry import get_platform
    import pytest

    with pytest.raises(KeyError):
        get_platform("amazon")
