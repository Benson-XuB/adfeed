from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adfeed.platforms.common.types import FeedExporter

_PLATFORMS: dict[str, "FeedExporter"] = {}


def register(platform: "FeedExporter") -> None:
    pid = str(getattr(platform, "id", "") or "").strip().lower()
    if not pid:
        raise ValueError("platform.id required")
    _PLATFORMS[pid] = platform


def get_platform(platform_id: str) -> "FeedExporter":
    pid = str(platform_id or "").strip().lower()
    if pid not in _PLATFORMS:
        raise KeyError(f"unknown platform: {platform_id}")
    return _PLATFORMS[pid]


def list_platform_ids() -> list[str]:
    return sorted(_PLATFORMS.keys())
