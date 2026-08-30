from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

PlatformId = Literal["google", "meta", "tiktok"]


@runtime_checkable
class FeedExporter(Protocol):
    id: str

    def export_feed(
        self,
        rows: list[dict],
        *,
        output_path: Path,
        country: str,
        shop_name: str = "",
        site_link: str = "",
        skip_out_of_stock: bool = False,
    ) -> int:
        """Write platform feed file; return item count."""
        ...
