#!/usr/bin/env python3
"""Clone a durable feed file to another country (local demo / UX testing)."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Demo-only: rough EN → DE for titles/colors so multi-market UI is visible in German.
_COLOR_EN_DE: list[tuple[str, str]] = [
    ("Navy Blue", "Marineblau"),
    ("Multicolor", "Mehrfarbig"),
    ("Apricot", "Aprikose"),
    ("Yellow", "Gelb"),
    ("Purple", "Lila"),
    ("Orange", "Orange"),
    ("Black", "Schwarz"),
    ("White", "Weiß"),
    ("Green", "Grün"),
    ("Brown", "Braun"),
    ("Beige", "Beige"),
    ("Khaki", "Khaki"),
    ("Pink", "Rosa"),
    ("Blue", "Blau"),
    ("Red", "Rot"),
    ("Gray", "Grau"),
    ("Grey", "Grau"),
]

_TITLE_PHRASE_EN_DE: list[tuple[str, str]] = [
    ("Women&#39;s ", "Damen "),
    ("Women's ", "Damen "),
    ("High Waist", "Hohe Taille"),
    ("Sleeveless", "Ärmellos"),
    ("Floral ", "Blumen-"),
    ("Denim Jeans", "Jeans"),
    ("Dress", "Kleid"),
    ("Skirt", "Rock"),
    ("Jacket", "Jacke"),
    ("Shirt", "Hemd"),
    ("Pants", "Hose"),
    ("Size", "Größe"),
    ("Regular fit", "Regular Fit"),
    ("Casual", "Lässig"),
]

_DESC_PHRASE_EN_DE: list[tuple[str, str]] = [
    ("Color:", "Farbe:"),
    ("Style:", "Stil:"),
    ("Fabric:", "Stoff:"),
    ("Fit Type:", "Passform:"),
    ("Occasion:", "Anlass:"),
    ("Length:", "Länge:"),
    ("Waistline:", "Taillenhöhe:"),
    ("Closure Type:", "Verschluss:"),
    ("Gender:", "Geschlecht:"),
    ("Size chart: see product page.", "Größentabelle: siehe Produktseite."),
    ("Long pants", "Lange Hose"),
    ("High waist", "Hohe Taille"),
    ("Private fashion, noble lady", "Eleganter Alltagsstil"),
    ("Unisex", "Unisex"),
    ("female", "Damen"),
    ("male", "Herren"),
]


def _replace_phrases(text: str, pairs: list[tuple[str, str]]) -> str:
    out = text
    for src, dst in pairs:
        out = out.replace(src, dst)
    return out


def _replace_colors(text: str) -> str:
    out = text
    for src, dst in _COLOR_EN_DE:
        out = re.sub(rf"\b{re.escape(src)}\b", dst, out, flags=re.IGNORECASE)
    return out


def _localize_tag(text: str, tag: str, transform) -> str:
    pattern = re.compile(rf"<g:{tag}>([^<]*)</g:{tag}>")

    def _sub(m: re.Match[str]) -> str:
        return f"<g:{tag}>{transform(m.group(1))}</g:{tag}>"

    return pattern.sub(_sub, text)


def apply_de_demo_locale(text: str) -> str:
    """Best-effort German demo copy — not production translation."""
    text = text.replace("United States Feed", "Germany Feed")
    text = text.replace("| United States |", "| Germany |")
    text = text.replace("for Google Shopping | United States |", "for Google Shopping | Germany |")

    text = _localize_tag(
        text,
        "color",
        lambda s: _replace_colors(s),
    )
    text = _localize_tag(
        text,
        "title",
        lambda s: _replace_colors(_replace_phrases(s, _TITLE_PHRASE_EN_DE)),
    )
    text = _localize_tag(
        text,
        "description",
        lambda s: _replace_colors(_replace_phrases(s, _DESC_PHRASE_EN_DE)),
    )
    return text


def apply_cn_demo_locale(text: str) -> str:
    """Best-effort Chinese demo copy — not production translation."""
    text = text.replace("United States Feed", "China Feed")
    text = text.replace("| United States |", "| China |")

    cn_colors = [
        ("Navy Blue", "藏青"),
        ("Multicolor", "多色"),
        ("Apricot", "杏色"),
        ("Yellow", "黄色"),
        ("Purple", "紫色"),
        ("Black", "黑色"),
        ("White", "白色"),
        ("Pink", "粉色"),
        ("Blue", "蓝色"),
        ("Red", "红色"),
        ("Orange", "橙色"),
    ]
    cn_title = [
        ("Women&#39;s", "女士"),
        ("Women's", "女士"),
        ("High Waist", "高腰"),
        ("Sleeveless", "无袖"),
        ("Floral", "印花"),
        ("Dress", "连衣裙"),
        ("Denim Jeans", "牛仔裤"),
        ("Size", "尺码"),
    ]

    def _cn_colors(s: str) -> str:
        out = s
        for src, dst in cn_colors:
            out = re.sub(rf"\b{re.escape(src)}\b", dst, out, flags=re.IGNORECASE)
        return out

    text = _localize_tag(text, "color", _cn_colors)
    text = _localize_tag(
        text,
        "title",
        lambda s: _cn_colors(_replace_phrases(s, cn_title)),
    )
    return text


def clone_feed(
    store_id: str,
    src_country: str,
    dst_country: str,
    *,
    platform: str = "google",
) -> dict:
    from adfeed.config import FEEDS_DIR, PUBLIC_BASE_URL
    from adfeed import store_db
    from adfeed.feed_preview import write_google_tsv_from_xml
    from adfeed.multi_platform_feeds import durable_feed_path, durable_feed_url

    src = src_country.upper()
    dst = dst_country.upper()
    plat = platform.lower()
    src_path = durable_feed_path(FEEDS_DIR, store_id, plat, src)
    dst_path = durable_feed_path(FEEDS_DIR, store_id, plat, dst)
    if not src_path.exists():
        raise FileNotFoundError(f"Source feed missing: {src_path}")

    text = src_path.read_text(encoding="utf-8")
    text = text.replace(f"{src} Feed", f"{dst} Feed")
    text = re.sub(
        rf"\|\s*{re.escape(src)}\s*\|",
        f"| {dst} |",
        text,
        count=1,
    )
    if dst == "DE":
        text = text.replace(" USD</g:price>", " EUR</g:price>")
        text = text.replace(" USD</g:", " EUR</g:")
        text = text.replace("currency=USD", "currency=EUR")
        text = text.replace("<g:country>US</g:country>", "<g:country>DE</g:country>")
        text = text.replace(
            "<g:size_system>US</g:size_system>",
            "<g:size_system>DE</g:size_system>",
        )
        text = apply_de_demo_locale(text)
    elif dst == "CN":
        text = text.replace(" USD</g:price>", " CNY</g:price>")
        text = text.replace(" USD</g:", " CNY</g:")
        text = text.replace("currency=USD", "currency=CNY")
        text = text.replace("<g:country>US</g:country>", "<g:country>CN</g:country>")
        text = apply_cn_demo_locale(text)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(text, encoding="utf-8")
    item_count = write_google_tsv_from_xml(dst_path, dst_path.with_suffix(".csv"))
    feed_url = durable_feed_url(PUBLIC_BASE_URL, store_id, plat, dst)
    store_db.save_feed_file(
        store_id=store_id,
        country=dst,
        platform=plat,
        file_path=str(dst_path),
        feed_url=feed_url,
        item_count=item_count,
    )
    return {
        "store_id": store_id,
        "platform": plat,
        "from": src,
        "to": dst,
        "path": str(dst_path),
        "item_count": item_count,
        "url": feed_url,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Clone durable feed to another country")
    p.add_argument("--store-id", required=True)
    p.add_argument("--from", dest="src", default="US")
    p.add_argument("--to", dest="dst", required=True)
    p.add_argument("--platform", default="google")
    args = p.parse_args()
    out = clone_feed(args.store_id, args.src, args.dst, platform=args.platform)
    print(out)


if __name__ == "__main__":
    main()
