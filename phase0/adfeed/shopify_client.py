"""Shopify 集成模块 — OAuth 授权 + 产品拉取 + 字段映射"""
import os
import secrets
import logging
from typing import Optional
from urllib.parse import urlencode

import httpx

from .config import (
    SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET,
    SHOPIFY_REDIRECT_URI, SHOPIFY_SCOPES, SHOPIFY_API_VERSION,
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
    """获取店铺基本信息"""
    shop = shop_domain.replace(".myshopify.com", "").strip()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://{shop}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/shop.json",
                headers={"X-Shopify-Access-Token": access_token},
            )
            if resp.status_code != 200:
                return None
            data = resp.json().get("shop", {})
            return {
                "name": data.get("name", ""),
                "domain": data.get("myshopify_domain", shop_domain),
                "email": data.get("email", ""),
            }
    except Exception as e:
        logger.error(f"Shopify shop info error: {e}")
        return None


# ═══════════════ 产品拉取 ═══════════════

async def fetch_shopify_products(shop_domain: str, access_token: str,
                                  limit: int = 250, page_info: str = None) -> dict:
    """从 Shopify 拉取产品列表

    Returns:
        {
            "products": [mapped_product_dict, ...],
            "next_page_info": "..." or None,
            "total_count": int,
        }
    """
    shop = shop_domain.replace(".myshopify.com", "").strip()
    headers = {"X-Shopify-Access-Token": access_token}
    params = {"limit": min(limit, 250), "fields": "id,title,handle,vendor,product_type,variants,images,tags,status,created_at"}

    if page_info:
        params["page_info"] = page_info

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://{shop}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json",
                headers=headers,
                params=params,
            )
            if resp.status_code != 200:
                logger.error(f"Shopify products fetch failed: {resp.status_code}")
                return {"products": [], "next_page_info": None, "total_count": 0}

            data = resp.json()
            raw_products = data.get("products", [])

            # 解析分页信息
            next_page_info = None
            link_header = resp.headers.get("Link", "")
            if 'rel="next"' in link_header:
                # 从 Link header 提取 page_info
                import re
                match = re.search(r'page_info=([^&"]+)', link_header)
                if match:
                    next_page_info = match.group(1)

            # 获取总数
            total_count = len(raw_products)
            try:
                count_resp = await client.get(
                    f"https://{shop}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products/count.json",
                    headers=headers,
                )
                if count_resp.status_code == 200:
                    total_count = count_resp.json().get("count", total_count)
            except Exception:
                pass

            # 映射为我们的格式
            mapped = [_map_shopify_product(p) for p in raw_products]

            return {
                "products": mapped,
                "next_page_info": next_page_info,
                "total_count": total_count,
            }
    except Exception as e:
        logger.error(f"Shopify products fetch error: {e}")
        return {"products": [], "next_page_info": None, "total_count": 0}


def _map_shopify_product(product: dict) -> dict:
    """将 Shopify 产品数据映射为 pipeline 需要的格式"""
    variants = product.get("variants", [])
    images = product.get("images", [])

    # 取第一个 variant 的信息
    first_variant = variants[0] if variants else {}
    sku = first_variant.get("sku", "") or str(product.get("id", ""))
    price = first_variant.get("price", "0")
    inventory = first_variant.get("inventory_quantity", 1) or 1

    # 所有 variant 的价格范围
    prices = [float(v.get("price", 0)) for v in variants if v.get("price")]
    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 0

    return {
        # pipeline 需要的字段
        "SKU": sku,
        "标题": product.get("title", ""),
        "描述": _strip_html(product.get("body_html", "")),
        "价格": min_price,
        "图片链接": images[0].get("src", "") if images else "",
        "附加图片": ",".join(img.get("src", "") for img in images[1:4]) if len(images) > 1 else "",
        "分类": product.get("product_type", "") or product.get("vendor", ""),
        "品牌": product.get("vendor", ""),
        "材质": "",  # Shopify 标准字段里没有材质
        "颜色": "",  # 需要从 variant options 提取
        "尺码": "",  # 需要从 variant options 提取
        "库存": inventory,

        # 额外信息（供前端展示）
        "shopify_id": str(product.get("id", "")),
        "shopify_handle": product.get("handle", ""),
        "shopify_status": product.get("status", ""),
        "shopify_tags": product.get("tags", []),
        "variant_count": len(variants),
        "image_count": len(images),
        "price_range": f"${min_price:.2f} - ${max_price:.2f}" if min_price != max_price else f"${min_price:.2f}",
        "created_at": product.get("created_at", ""),
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
