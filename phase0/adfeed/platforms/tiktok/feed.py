"""TikTok Shop catalog CSV export — no invented weight/package dims."""

from __future__ import annotations

import csv
import html
import io
import json
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

_GPC_TO_TIKTOK_CATEGORY = {
    "4174": "Women's Clothing > Dresses",
    "2271": "Women's Clothing > Tops",
    "209": "Women's Clothing > Jeans",
    "5423": "Women's Clothing > Jackets & Coats",
    "5598": "Women's Clothing > Sweaters",
    "6228": "Women's Clothing > Skirts",
    "3913": "Women's Clothing > Pants",
    "207": "Women's Clothing > Shirts & Blouses",
    "502999": "Women's Clothing > Jumpsuits & Rompers",
    "3032": "Socks & Hosiery",
    "2923": "Socks & Hosiery",
}


def _gpc_to_tiktok_category(gpc_code: str, gpc_path: str = "") -> str:
    if gpc_code in _GPC_TO_TIKTOK_CATEGORY:
        return _GPC_TO_TIKTOK_CATEGORY[gpc_code]
    if gpc_path:
        return gpc_path
    return "General"


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
