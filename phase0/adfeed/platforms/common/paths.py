"""Shared durable feed path / public URL helpers."""

from __future__ import annotations

from pathlib import Path


def durable_feed_path(feeds_dir: Path, store_id: str, platform: str, language: str) -> Path:
    """FEEDS_DIR/{store_id}/{platform}/{lang}.{xml|csv}"""
    plat = platform.lower()
    lang = language.lower()
    ext = "csv" if plat == "tiktok" else "xml"
    return feeds_dir / store_id / plat / f"{lang}.{ext}"


def durable_feed_url(public_base: str, store_id: str, platform: str, language: str) -> str:
    plat = platform.lower()
    lang = language.lower()
    ext = "csv" if plat == "tiktok" else "xml"
    return f"{public_base.rstrip('/')}/feeds/{store_id}/{plat}/{lang}.{ext}"
