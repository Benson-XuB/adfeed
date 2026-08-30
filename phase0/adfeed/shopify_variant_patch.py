"""Write color/size to Shopify variant options (Admin GraphQL)."""
from __future__ import annotations

import logging
from typing import Any, Optional

from .product_attr_check import _blank_color, _blank_size
from .shopify_admin_gql import fetch_product, graphql_payload, numeric_id
from .store_sync import _option_maps, _variant_color_size

logger = logging.getLogger("adfeed-shopify-variant-patch")

_COLOR_KEYS = ("color", "colour", "farbe", "颜色", "couleur")
_SIZE_KEYS = ("size", "größe", "taille", "尺码", "sizing")

_VARIANT_BULK_UPDATE = """
mutation BulkPatchVariantOptions($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
  productVariantsBulkUpdate(productId: $productId, variants: $variants) {
    productVariants {
      id
      sku
      selectedOptions { name value }
    }
    userErrors { field message }
  }
}
"""

_OPTION_RENAME = """
mutation RenameOptionValue(
  $productId: ID!,
  $option: OptionUpdateInput!,
  $optionValuesToUpdate: [OptionValueUpdateInput!]
) {
  productOptionUpdate(
    productId: $productId,
    option: $option,
    optionValuesToUpdate: $optionValuesToUpdate
  ) {
    product { id }
    userErrors { field message }
  }
}
"""

_PRODUCT_OPTIONS = """
query ProductOptions($id: ID!) {
  product(id: $id) {
    options { id name position optionValues { id name } }
  }
}
"""


def _find_option_name(product: dict[str, Any], field: str) -> Optional[str]:
    keys = _COLOR_KEYS if field == "color" else _SIZE_KEYS
    for opt in product.get("options") or []:
        name = str(opt.get("name") or "").strip()
        low = name.lower()
        if any(k in low for k in keys):
            return name
    # Color only: Title-only Shopify demos can rename option1 (Default Title → Black).
    # Never invent a Size option from option2 — that dead-ends Fix on snowboards.
    if field == "color":
        opts = sorted(product.get("options") or [], key=lambda o: int(o.get("position") or 0))
        if opts:
            return str(opts[0].get("name") or "").strip() or None
    return None


def _product_gid(product_id: str) -> str:
    return f"gid://shopify/Product/{numeric_id(product_id)}"


def _variant_gid(variant_id: str) -> str:
    return f"gid://shopify/ProductVariant/{numeric_id(variant_id)}"


def _graphql_errors_message(payload: dict) -> str:
    for err in payload.get("errors") or []:
        msg = str(err.get("message") or err)
        low = msg.lower()
        if "access" in low and "denied" in low:
            return "write_products scope required — reopen the app and approve access"
        if "not authorized" in low or "required access" in low:
            return "write_products scope required — reopen the app and approve access"
        return msg
    return ""


def _blank(field: str, val: str) -> bool:
    return _blank_color(val) if field == "color" else _blank_size(val)


def _sku_filter_match(sku: str, skus: set[str]) -> bool:
    """Empty skus set means apply to every variant (demo products often lack SKUs)."""
    if not skus:
        return True
    return sku in skus


def _placeholder_values(
    product: dict[str, Any],
    field: str,
    skus: set[str],
) -> list[str]:
    """Distinct non-empty placeholder option values on selected SKUs."""
    pos_to_name, _ = _option_maps(product)
    seen: set[str] = set()
    out: list[str] = []
    for variant in product.get("variants") or []:
        sku = str(variant.get("sku") or "").strip()
        if not _sku_filter_match(sku, skus):
            continue
        color, size = _variant_color_size(variant, pos_to_name)
        val = str(color if field == "color" else size).strip()
        # Title-only Shopify demos keep "Default Title" on option1 — treat as placeholder.
        if not val:
            raw = str(variant.get("option1") or "").strip() if field == "color" else str(variant.get("option2") or "").strip()
            if raw and _blank(field, raw):
                val = raw
        if not val or not _blank(field, val):
            continue
        if val not in seen:
            seen.add(val)
            out.append(val)
    return out


def _skus_for_option_value(
    product: dict[str, Any],
    field: str,
    option_value: str,
    skus: set[str],
) -> list[str]:
    pos_to_name, _ = _option_maps(product)
    matched: list[str] = []
    for variant in product.get("variants") or []:
        sku = str(variant.get("sku") or "").strip()
        if not _sku_filter_match(sku, skus):
            continue
        color, size = _variant_color_size(variant, pos_to_name)
        val = str(color if field == "color" else size).strip()
        if not val and field == "color":
            val = str(variant.get("option1") or "").strip()
        if val == option_value:
            matched.append(sku or str(variant.get("id") or "ok"))
    return matched


def _fetch_option_meta(shop_domain: str, access_token: str, product_id: str) -> list[dict[str, Any]]:
    payload = graphql_payload(
        shop_domain,
        access_token,
        _PRODUCT_OPTIONS,
        {"id": _product_gid(product_id)},
    )
    product = (payload.get("data") or {}).get("product") or {}
    return list(product.get("options") or [])


def _rename_option_value(
    shop_domain: str,
    access_token: str,
    product_id: str,
    option_name: str,
    old_value: str,
    new_value: str,
) -> tuple[bool, str]:
    options = _fetch_option_meta(shop_domain, access_token, product_id)
    opt = next((o for o in options if str(o.get("name") or "") == option_name), None)
    if not opt:
        return False, f"Product has no {option_name} option"
    old_val = str(old_value or "").strip()
    new_val = str(new_value or "").strip()
    if not old_val:
        return False, "Original option value is empty — cannot rename"
    if old_val == new_val:
        return True, ""
    ov = next(
        (v for v in (opt.get("optionValues") or []) if str(v.get("name") or "") == old_val),
        None,
    )
    if not ov:
        return False, f"Option value {old_val} does not exist"
    existing = {str(v.get("name") or "") for v in (opt.get("optionValues") or [])}
    if new_val in existing and new_val != old_val:
        return False, f"Color {new_val} already exists — pick another name or merge variants in Shopify"

    payload = graphql_payload(
        shop_domain,
        access_token,
        _OPTION_RENAME,
        {
            "productId": _product_gid(product_id),
            "option": {"id": opt.get("id")},
            "optionValuesToUpdate": [{"id": ov.get("id"), "name": new_val}],
        },
    )
    top_err = _graphql_errors_message(payload)
    if top_err:
        return False, top_err
    block = (payload.get("data") or {}).get("productOptionUpdate") or {}
    user_errors = list(block.get("userErrors") or [])
    if user_errors:
        return False, "; ".join(str(e.get("message") or e) for e in user_errors)
    return True, ""


def _try_option_rename(
    shop_domain: str,
    access_token: str,
    product: dict[str, Any],
    field: str,
    new_value: str,
    skus: set[str],
) -> Optional[dict[str, Any]]:
    """Rename shared placeholder option values (e.g. Style 1 → Black, OSFA text → M)."""
    option_name = _find_option_name(product, field)
    if not option_name:
        return None

    placeholders = _placeholder_values(product, field, skus)
    if not placeholders:
        return None

    target = str(new_value or "").strip()
    if not target:
        return None

    first = placeholders[0]
    ok, err = _rename_option_value(
        shop_domain,
        access_token,
        str(product.get("id") or ""),
        option_name,
        first,
        target,
    )
    if not ok:
        logger.warning(
            "shopify_variant_patch rename failed product=%s field=%s %r→%r err=%s",
            product.get("id"),
            field,
            first,
            target,
            err,
        )
        return {
            "updated": [],
            "missing": [],
            "errors": [{"sku": "", "message": err}],
            "message": err,
            "debug": {"stage": "option_rename", "from": first, "to": target},
        }

    updated = _skus_for_option_value(product, field, first, skus)
    remaining = placeholders[1:]
    message = f"Renamed {first} → {target} ({len(updated)} variants)"
    if remaining:
        message += f". Still pending: {', '.join(remaining)} — save again"
    logger.info(
        "shopify_variant_patch rename ok product=%s field=%s %r→%r updated=%d remaining=%s",
        product.get("id"),
        field,
        first,
        target,
        len(updated),
        remaining,
    )
    return {
        "updated": updated,
        "missing": [],
        "errors": [],
        "message": message,
        "partial": bool(remaining),
        "remaining_placeholders": remaining,
        "debug": {
            "stage": "option_rename",
            "from": first,
            "to": target,
            "remaining": remaining,
        },
    }


def _bulk_variant_update(
    shop_domain: str,
    access_token: str,
    product_id: str,
    bulk_inputs: list[dict[str, Any]],
    missing: list[str],
    errors: list[dict[str, str]],
    color_opt: Optional[str],
    size_opt: Optional[str],
) -> dict[str, Any]:
    pid = numeric_id(product_id)
    payload = graphql_payload(
        shop_domain,
        access_token,
        _VARIANT_BULK_UPDATE,
        {
            "productId": _product_gid(pid),
            "variants": bulk_inputs,
        },
    )
    top_err = _graphql_errors_message(payload)
    if top_err:
        logger.error("shopify_variant_patch graphql error product=%s err=%s", pid, top_err)
        return {
            "updated": [],
            "missing": missing,
            "errors": [{"sku": "", "message": top_err}],
            "message": top_err,
            "need_reauth": "write_products" in top_err.lower() or "scope" in top_err.lower(),
            "debug": {"stage": "bulk_update", "graphql_errors": payload.get("errors")},
        }

    block = (payload.get("data") or {}).get("productVariantsBulkUpdate") or {}
    user_errors = list(block.get("userErrors") or [])
    if user_errors:
        err_msg = "; ".join(str(e.get("message") or e) for e in user_errors)
        logger.error("shopify_variant_patch userErrors product=%s err=%s", pid, err_msg)
        hint = ""
        low = err_msg.lower()
        if "already exists" in low:
            hint = (
                " (This product may have multiple color/size groups — save again or edit each group in Shopify.)"
            )
        return {
            "updated": [],
            "missing": missing,
            "errors": [{"sku": "", "message": err_msg + hint}],
            "message": err_msg + hint,
            "debug": {"stage": "bulk_update", "user_errors": user_errors},
        }

    updated_variants = list(block.get("productVariants") or [])
    # Demo / supplier variants often have empty SKUs — still count the write as success.
    updated = [
        str(v.get("sku") or "").strip() or str(v.get("id") or "ok")
        for v in updated_variants
    ]
    if not updated and bulk_inputs:
        updated = [str(i.get("id") or "ok") for i in bulk_inputs]
    message = (
        f"Wrote {len(updated)} variant(s) to Shopify"
        if updated
        else "Shopify returned no updates"
    )
    return {
        "updated": updated,
        "missing": missing,
        "errors": errors,
        "message": message,
        "debug": {
            "stage": "bulk_update",
            "color_opt": color_opt,
            "size_opt": size_opt,
            "requested": len(bulk_inputs),
            "returned": len(updated_variants),
        },
    }


def patch_shopify_variant_attrs(
    shop_domain: str,
    access_token: str,
    shopify_product_id: str,
    patches: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply color/size patches to Shopify variant options for one product."""
    pid = numeric_id(shopify_product_id)
    patch_skus = {str(p.get("sku") or "").strip() for p in patches if p.get("sku")}
    field = "color" if any(p.get("color") for p in patches) else "size"
    new_value = ""
    for p in patches:
        val = str(p.get(field) or "").strip()
        if val:
            new_value = val
            break

    logger.info(
        "shopify_variant_patch start shop=%s product=%s field=%s value=%r skus=%s",
        shop_domain,
        pid,
        field,
        new_value,
        sorted(patch_skus)[:8],
    )

    product = fetch_product(shop_domain, access_token, pid)
    if not product:
        return {
            "updated": [],
            "missing": sorted(patch_skus),
            "errors": [{"sku": "", "message": "Shopify product not found"}],
            "message": "Shopify product not found",
            "debug": {"stage": "fetch_product"},
        }

    color_opt = _find_option_name(product, "color")
    size_opt = _find_option_name(product, "size")

    # Soft-skip: cannot invent a Size option — merchant would hit a dead-end dialog.
    if field == "size" and not size_opt:
        return {
            "updated": ["skipped"],
            "missing": [],
            "errors": [],
            "message": "No Size option on this product — size not required. You can generate the feed.",
            "skipped_no_option": True,
            "need_size": False,
            "debug": {"stage": "skip_no_size_option"},
        }

    # Prefer option-value rename when variants share placeholder text (Style 1, OSFA…).
    rename_result = _try_option_rename(shop_domain, access_token, product, field, new_value, patch_skus)
    if rename_result is not None:
        return rename_result

    variants = list(product.get("variants") or [])
    sku_to_variant = {
        str(v.get("sku") or "").strip(): v for v in variants if v.get("sku")
    }
    bulk_inputs: list[dict[str, Any]] = []
    missing: list[str] = []
    errors: list[dict[str, str]] = []

    # Empty SKU patches (or no SKUs on product) → write the same color/size to all variants.
    apply_all = (not patch_skus) or any(
        not str(p.get("sku") or "").strip() for p in patches
    )
    work_patches: list[dict[str, Any]]
    if apply_all and new_value:
        work_patches = [
            {"sku": str(v.get("sku") or "").strip(), field: new_value, "id": v.get("id")}
            for v in variants
        ]
    else:
        work_patches = list(patches)

    for patch in work_patches:
        sku = str(patch.get("sku") or "").strip()
        variant = sku_to_variant.get(sku) if sku else None
        if not variant and patch.get("id"):
            variant = next(
                (v for v in variants if str(v.get("id") or "") == str(patch.get("id"))),
                None,
            )
        if not variant and apply_all and not sku:
            # Already expanded from variants above with id.
            continue
        if not variant:
            if sku:
                missing.append(sku)
            continue

        option_values: list[dict[str, str]] = []
        color_val = str(patch.get("color") or "").strip()
        size_val = str(patch.get("size") or "").strip()
        label = sku or str(variant.get("id") or "")
        if color_val:
            if not color_opt:
                errors.append({"sku": label, "message": "No Color option on this product — add one in Shopify"})
                continue
            option_values.append({"optionName": color_opt, "name": color_val})
        if size_val:
            if not size_opt:
                errors.append({"sku": label, "message": "No Size option on this product — add one in Shopify"})
                continue
            option_values.append({"optionName": size_opt, "name": size_val})
        if not option_values:
            continue
        bulk_inputs.append({
            "id": _variant_gid(str(variant.get("id") or "")),
            "optionValues": option_values,
        })

    if not bulk_inputs:
        message = errors[0]["message"] if errors else "No variants to write"
        if missing and not errors:
            message = "Matching variant SKUs not found"
        return {
            "updated": [],
            "missing": missing,
            "errors": errors,
            "message": message,
            "debug": {"stage": "no_inputs", "missing": missing},
        }

    return _bulk_variant_update(
        shop_domain,
        access_token,
        pid,
        bulk_inputs,
        missing,
        errors,
        color_opt,
        size_opt,
    )
