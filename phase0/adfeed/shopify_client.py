"""Shopify 集成模块 — OAuth 授权 + 产品拉取 + 字段映射 + v3.0 脏词清洗/属性标准化"""
import os
import secrets
import logging
from typing import Optional
from urllib.parse import urlencode

import httpx

from .config import (
    SHOPIFY_CLIENT_ID,
    SHOPIFY_CLIENT_SECRET,
    SHOPIFY_REDIRECT_URI,
    SHOPIFY_SCOPES,
)
from .db import (
    create_shopify_connection, get_shopify_connection, delete_shopify_connection,
    ShopifyConnection,
)

logger = logging.getLogger("adfeed-api")


# ═══════════════ OAuth ═══════════════

def get_shopify_auth_url(shop_domain: str) -> str:
    """生成 Shopify OAuth 授权链接

    Args:
        shop_domain: 店铺域名，如 "mystore" 或 "mystore.myshopify.com"
    """
    # 标准化域名
    shop = shop_domain.replace(".myshopify.com", "").strip()

    params = {
        "client_id": SHOPIFY_CLIENT_ID,
        "scope": SHOPIFY_SCOPES,
        "redirect_uri": SHOPIFY_REDIRECT_URI,
        "state": secrets.token_urlsafe(16),
    }
    url = f"https://{shop}.myshopify.com/admin/oauth/authorize?{urlencode(params)}"
    logger.info(f"Shopify auth URL for {shop}: {url[:80]}...")
    return url


async def exchange_shopify_code(shop_domain: str, code: str) -> Optional[dict]:
    """用授权码换 access_token

    Returns:
        {"access_token": "...", "scope": "..."} 或 None
    """
    shop = shop_domain.replace(".myshopify.com", "").strip()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://{shop}.myshopify.com/admin/oauth/access_token",
                data={
                    "client_id": SHOPIFY_CLIENT_ID,
                    "client_secret": SHOPIFY_CLIENT_SECRET,
                    "code": code,
                },
            )
            if resp.status_code != 200:
                logger.error(f"Shopify token exchange failed: {resp.status_code} {resp.text}")
                return None

            data = resp.json()
            return {
                "access_token": data.get("access_token", ""),
                "scope": data.get("scope", ""),
            }
    except Exception as e:
        logger.error(f"Shopify token exchange error: {e}")
        return None


async def get_shop_info(shop_domain: str, access_token: str) -> Optional[dict]:
    """获取店铺基本信息（Admin GraphQL）。"""
    try:
        from .shopify_admin_gql import fetch_shop
        data = fetch_shop(shop_domain, access_token)
        if not data.get("name") and not data.get("myshopify_domain"):
            return None
        return {
            "name": data.get("name", ""),
            "domain": data.get("myshopify_domain") or shop_domain,
            "email": data.get("email", ""),
            "currency": str(data.get("currency") or "").strip().upper(),
        }
    except Exception as e:
        logger.error(f"Shopify shop info error: {e}")
        return None


# ═══════════════ 产品拉取 ═══════════════

async def fetch_shopify_products(
    shop_domain: str,
    access_token: str,
    limit: int = 250,
    page_info: str = None,
    *,
    lite: bool = False,
) -> dict:
    """从 Shopify 拉取产品列表

    Returns:
        {
            "products": [mapped_product_dict, ...],
            "next_page_info": "..." or None,
            "total_count": int,
        }
    """
    shop = shop_domain.replace(".myshopify.com", "").strip()
    try:
        from .shopify_admin_gql import fetch_products_page
        page = fetch_products_page(
            shop_domain,
            access_token,
            limit=min(limit, 100),
            cursor=page_info,
            lite=lite,
        )
        mapped = [
            _map_shopify_product(p, shop + ".myshopify.com") for p in page.get("products") or []
        ]
        return {
            "products": mapped,
            "next_page_info": page.get("next_page_info"),
            "total_count": page.get("total_count") or len(mapped),
        }
    except Exception as e:
        logger.error(f"Shopify products fetch error: {e}")
        return {"products": [], "next_page_info": None, "total_count": 0}


def _map_shopify_product(product: dict, shop_domain: str = "") -> dict:
    """将 Shopify 产品数据映射为 pipeline 需要的格式

    v3.0: 链接使用产品页 URL / 变体颜色尺码提取 / 脏词清洗
    """
    from .dirty_word_filter import clean_dirty_words

    variants = product.get("variants", [])
    images = product.get("images", [])
    handle = product.get("handle", "")

    # 取第一个 variant 的信息
    first_variant = variants[0] if variants else {}
    sku = first_variant.get("sku", "") or str(product.get("id", ""))
    price = first_variant.get("price", "0")
    inventory = first_variant.get("inventory_quantity", 1) or 1

    # 所有 variant 的价格范围
    prices = [float(v.get("price", 0)) for v in variants if v.get("price")]
    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 0

    # v3.0: 从 variant options 提取颜色/尺码
    color = ""
    size = ""
    for v in variants:
        opt1 = v.get("option1", "") or ""
        opt2 = v.get("option2", "") or ""
        opt3 = v.get("option3", "") or ""
        # 启发式：通常 option1=颜色, option2=尺码，或反过来
        for opt in [opt1, opt2, opt3]:
            opt_lower = opt.lower().strip()
            if not opt_lower or opt_lower == "default title" or opt_lower == "default":
                continue
            if not color and any(c in opt_lower for c in ["red", "blue", "black", "white", "green", "pink", "brown", "gray", "grey", "gold", "silver", "purple", "orange", "beige", "navy", "khaki"]):
                color = opt
            elif not size and opt_lower in ("xs", "s", "m", "l", "xl", "xxl", "one size", "free size"):
                size = opt
        if color and size:
            break
    # 回退：从 option1/option2 名称推断
    if not color and not size:
        options = product.get("options", [])
        for opt_group in options:
            opt_name = (opt_group.get("name", "") or "").lower()
            if "color" in opt_name or "colour" in opt_name or "farbe" in opt_name:
                color = first_variant.get(f"option{opt_group.get('position', 1)}", "")
            elif "size" in opt_name or "größe" in opt_name or "taille" in opt_name:
                size = first_variant.get(f"option{opt_group.get('position', 1)}", "")

    # v3.0: 脏词清洗标题
    raw_title = product.get("title", "")
    dirty_result = clean_dirty_words(raw_title)
    clean_title = dirty_result["clean_title"] or raw_title

    # v3.0: 产品页链接
    if shop_domain and handle:
        product_link = f"https://{shop_domain}/products/{handle}"
    else:
        product_link = ""

    from .product_attr_check import check_shopify_product_attrs
    gaps = check_shopify_product_attrs(product)

    return {
        # pipeline 需要的字段
        "SKU": sku,
        "标题": clean_title,
        "描述": _strip_html(product.get("body_html", "")),
        "价格": min_price,
        "图片链接": images[0].get("src", "") if images else "",
        "附加图片": ",".join(img.get("src", "") for img in images[1:4]) if len(images) > 1 else "",
        "分类": product.get("product_type", "") or product.get("vendor", ""),
        "品牌": product.get("vendor", ""),
        "材质": "",  # Shopify 标准字段里没有材质
        "颜色": color,
        "尺码": size,
        "库存": inventory,
        "链接": product_link,

        # 额外信息（供前端展示）
        "shopify_id": str(product.get("id", "")),
        "shopify_handle": handle,
        "shopify_status": product.get("status", ""),
        "shopify_tags": product.get("tags", []),
        "variant_count": int(product.get("total_variant_count") or len(variants)),
        "image_count": len(images),
        "price_range": f"${min_price:.2f} - ${max_price:.2f}" if min_price != max_price else f"${min_price:.2f}",
        "created_at": product.get("created_at", ""),
        "product_type": product.get("product_type", "") or "",
        "need_color": gaps["need_color"],
        "need_size": gaps["need_size"],
        "variant_skus": [
            (str(v.get("sku") or "").strip() or f"{product.get('id')}-{v.get('id')}")
            for v in variants
        ],
    }


def _strip_html(html: str) -> str:
    """简单去除 HTML 标签"""
    import re
    return re.sub(r'<[^>]+>', '', html).strip()


# ═══════════════ 连接管理 ═══════════════

async def connect_shopify_store(user_id: str, shop_domain: str, code: str) -> Optional[dict]:
    """完整的 Shopify 连接流程：换 token → 获取店铺信息 → 存储

    Returns:
        {"ok": True, "shop_domain": "...", "shop_name": "..."} 或 None
    """
    # 1. 换 access_token
    token_data = await exchange_shopify_code(shop_domain, code)
    if not token_data:
        return None

    access_token = token_data["access_token"]

    # 2. 获取店铺信息
    shop_info = await get_shop_info(shop_domain, access_token)
    shop_name = shop_info.get("name", shop_domain) if shop_info else shop_domain

    # 3. 存储连接
    conn = create_shopify_connection(
        user_id=user_id,
        shop_domain=shop_domain.replace(".myshopify.com", "").strip() + ".myshopify.com",
        shop_name=shop_name,
        access_token=access_token,
    )

    logger.info(f"Shopify store connected: {shop_name} ({conn.shop_domain}) for user {user_id[:8]}")

    return {
        "ok": True,
        "shop_domain": conn.shop_domain,
        "shop_name": conn.shop_name,
    }
