"""Google Shopping feed export."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from adfeed.feed_generator import generate as generate_feed_xml


def generate_google_feed_xml(
    rows: list[dict],
    country: str,
    *,
    skip_out_of_stock: bool = False,
) -> str:
    df = pd.DataFrame(rows) if not isinstance(rows, pd.DataFrame) else rows
    return generate_feed_xml(df, country, skip_out_of_stock=skip_out_of_stock)


def save_google_feed(
    rows: list[dict],
    output_path: Path,
    country: str,
    *,
    skip_out_of_stock: bool = False,
) -> int:
    xml = generate_google_feed_xml(rows, country, skip_out_of_stock=skip_out_of_stock)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(xml, encoding="utf-8")
    return xml.count("<item>")


class GooglePlatform:
    id = "google"

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
        return save_google_feed(
            rows, output_path, country, skip_out_of_stock=skip_out_of_stock
        )
