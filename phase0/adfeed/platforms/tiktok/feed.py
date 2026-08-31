"""TikTok Shop catalog CSV export — no invented weight/package dims."""

from __future__ import annotations

import csv
import html
import io
import json
import re
from pathlib import Path

TIKTOK_CSV_FIELDS = [
    "Product ID",
    "Product Name",
    "Description",
    "Brand",
    "Category",
    "Variant ID",
    "Variant Name",
    "Price",
    "Sale Price",
    "Stock",
    "Status",
    "Main Image",
    "Additional Images",
    "Weight (kg)",
    "Package Length (cm)",
    "Package Width (cm)",
    "Package Height (cm)",
    "Color",
    "Size",
    "Gender",
    "Material",
]

# Code map aligned with AdFeed gpc_matcher aliases (not always official Google IDs).
# Prefer path keywords in _gpc_to_tiktok_category when both are present.
_GPC_TO_TIKTOK_CATEGORY = {
    "4174": "Women's Clothing > Dresses",
    "2271": "Women's Clothing > Dresses",
    "204": "Women's Clothing > Pants",
    "209": "Socks & Hosiery",
    "212": "Women's Clothing > Tops",
    "1831": "Women's Clothing > Jackets & Coats",
    "5250": "Women's Clothing > Jumpsuits & Rompers",
    "5423": "Women's Clothing > Jackets & Coats",
    "5598": "Women's Clothing > Jackets & Coats",
    "6228": "Women's Clothing > Skirts",
    "3913": "Women's Clothing > Pants",
    "207": "Women's Clothing > Shirts & Blouses",
    "502999": "Women's Clothing > Jumpsuits & Rompers",
    "3032": "Socks & Hosiery",
    "2923": "Socks & Hosiery",
}

# Path needles → TikTok category. Order matters (more specific first).
_GPC_PATH_TO_TIKTOK = (
    ("jumpsuit", "Women's Clothing > Jumpsuits & Rompers"),
    ("romper", "Women's Clothing > Jumpsuits & Rompers"),
    ("one-pieces", "Women's Clothing > Jumpsuits & Rompers"),
    ("dresses", "Women's Clothing > Dresses"),
    ("dress", "Women's Clothing > Dresses"),
    ("jeans", "Women's Clothing > Jeans"),
    ("skirts", "Women's Clothing > Skirts"),
    ("skirt", "Women's Clothing > Skirts"),
    ("vests", "Women's Clothing > Jackets & Coats"),
    ("vest", "Women's Clothing > Jackets & Coats"),
    ("coats & jackets", "Women's Clothing > Jackets & Coats"),
    ("jackets", "Women's Clothing > Jackets & Coats"),
    ("jacket", "Women's Clothing > Jackets & Coats"),
    ("coats", "Women's Clothing > Jackets & Coats"),
    ("socks", "Socks & Hosiery"),
    ("sweaters", "Women's Clothing > Sweaters"),
    ("sweater", "Women's Clothing > Sweaters"),
    ("pants", "Women's Clothing > Pants"),
    ("shirts & tops", "Women's Clothing > Tops"),
    ("shirts", "Women's Clothing > Shirts & Blouses"),
    ("tops", "Women's Clothing > Tops"),
)


_JEANS_HINT = re.compile(r"\b(jeans?|denim)\b|牛仔", re.I)


def _looks_like_jeans(*texts: str) -> bool:
    blob = " ".join(t for t in texts if t)
    return bool(_JEANS_HINT.search(blob))


def _gpc_to_tiktok_category(
    gpc_code: str, gpc_path: str = "", *, title: str = ""
) -> str:
    """Map Google GPC → TikTok category.

    Google taxonomy has no Jeans leaf (jeans alias → Pants/204). When the
    mapped category is Pants but the title signals jeans/denim, use TikTok's
    Jeans category — Google/Meta feeds stay on GPC 204.
    """
    path_l = (gpc_path or "").lower()
    cat = ""
    for needle, mapped in _GPC_PATH_TO_TIKTOK:
        if needle in path_l:
            cat = mapped
            break
    if not cat and gpc_code in _GPC_TO_TIKTOK_CATEGORY:
        cat = _GPC_TO_TIKTOK_CATEGORY[gpc_code]
    if not cat and gpc_path:
        cat = gpc_path
    if not cat:
        cat = "General"

    if cat == "Women's Clothing > Pants" and _looks_like_jeans(title, gpc_path):
        return "Women's Clothing > Jeans"
    return cat


def _weight_kg_from_row(row: dict) -> str:
    """Only pass through known weight fields — never invent."""
    for key in ("weight_kg", "Weight (kg)", "重量", "shipping_weight"):
        raw = row.get(key)
        if raw is None or raw == "":
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            s = str(raw).strip()
            return s
        if val > 0:
            return f"{val:.2f}"
    return ""


def _dim_from_row(row: dict, *keys: str) -> str:
    for key in keys:
        raw = row.get(key)
        if raw is None or raw == "":
            continue
        s = str(raw).strip()
        if s and s != "nan":
            return s
    return ""


def generate_tiktok_feed(rows: list[dict], shop_name: str = "") -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=TIKTOK_CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()

    product_groups: dict[str, list[dict]] = {}
    for row in rows:
        group_id = str(row.get("item_group_id", row.get("SKU", "")))
        product_groups.setdefault(group_id, []).append(row)

    for group_id, variants in product_groups.items():
        first = variants[0]
        product_name = str(first.get("优化后标题", first.get("标题", "")))
        description = html.unescape(str(first.get("描述", "")))
        brand = str(first.get("品牌", ""))
        category = _gpc_to_tiktok_category(
            str(first.get("GPC代码", "")),
            str(first.get("GPC路径", "")),
            title=product_name,
        )
        main_image = str(first.get("图片链接", ""))

        all_additional = []
        seen_imgs = {main_image}
        for v in variants:
            raw = str(v.get("附加图片", ""))
            if raw and raw != "nan":
                try:
                    imgs = json.loads(raw)
                    if isinstance(imgs, list):
                        for img in imgs:
                            if img and img not in seen_imgs:
                                all_additional.append(img)
                                seen_imgs.add(img)
                except (json.JSONDecodeError, TypeError):
                    for img in raw.split(","):
                        img = img.strip()
                        if img and img not in seen_imgs:
                            all_additional.append(img)
                            seen_imgs.add(img)

        additional_images = ";".join(all_additional[:5])

        for v in variants:
            variant_id = str(v.get("SKU", ""))
            color = str(v.get("颜色", ""))
            size = str(v.get("尺码", ""))
            variant_parts = [p for p in (color, size) if p]
            variant_name = " - ".join(variant_parts) if variant_parts else variant_id
            price = float(v.get("价格", 0) or 0)
            stock = int(v.get("库存", 0) or 0)
            status = "Active" if stock > 0 else "Inactive"

            writer.writerow(
                {
                    "Product ID": group_id,
                    "Product Name": html.unescape(product_name),
                    "Description": description,
                    "Brand": brand,
                    "Category": category,
                    "Variant ID": variant_id,
                    "Variant Name": variant_name,
                    "Price": f"{price:.2f}",
                    "Sale Price": "",
                    "Stock": stock,
                    "Status": status,
                    "Main Image": main_image,
                    "Additional Images": additional_images,
                    "Weight (kg)": _weight_kg_from_row(v) or _weight_kg_from_row(first),
                    "Package Length (cm)": _dim_from_row(
                        v, "package_length_cm", "Package Length (cm)"
                    )
                    or _dim_from_row(first, "package_length_cm", "Package Length (cm)"),
                    "Package Width (cm)": _dim_from_row(
                        v, "package_width_cm", "Package Width (cm)"
                    )
                    or _dim_from_row(first, "package_width_cm", "Package Width (cm)"),
                    "Package Height (cm)": _dim_from_row(
                        v, "package_height_cm", "Package Height (cm)"
                    )
                    or _dim_from_row(first, "package_height_cm", "Package Height (cm)"),
                    "Color": color,
                    "Size": size,
                    "Gender": str(v.get("gender", "")),
                    "Material": str(v.get("材质", "")),
                }
            )

    return output.getvalue()


def save_tiktok_feed(rows: list[dict], output_path: Path, shop_name: str = "") -> int:
    csv_content = generate_tiktok_feed(rows, shop_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(csv_content, encoding="utf-8")
    return max(csv_content.count("\n") - 1, 0)


class TikTokPlatform:
    id = "tiktok"

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
        return save_tiktok_feed(rows, output_path, shop_name)
