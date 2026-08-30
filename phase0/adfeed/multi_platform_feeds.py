"""AdFeed AI — multi-platform feed helpers (compat re-exports).

Prefer `adfeed.platforms.{google,meta,tiktok}` and
`adfeed.platforms.common.paths` for new code.
"""

from adfeed.platforms.common.paths import durable_feed_path, durable_feed_url
from adfeed.platforms.meta.feed import generate_meta_feed, save_meta_feed
from adfeed.platforms.tiktok.feed import generate_tiktok_feed, save_tiktok_feed

__all__ = [
    "durable_feed_path",
    "durable_feed_url",
    "generate_meta_feed",
    "generate_tiktok_feed",
    "save_meta_feed",
    "save_tiktok_feed",
]
