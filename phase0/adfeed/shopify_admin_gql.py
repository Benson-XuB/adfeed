"""Shopify Admin GraphQL client — REST-shaped dicts for existing mappers.

Public App Store apps must not call Admin REST. Keep Python return shapes
compatible with shopify_client / store_sync / store_compliance.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from .config import SHOPIFY_API_VERSION

logger = logging.getLogger("adfeed-admin-gql")

PRODUCT_FIELDS = """
  id
  title
  handle
  vendor
  productType
  descriptionHtml
  status
  createdAt
  tags
  options { name position }
  variants(first: 100) {
    nodes {
      id
      sku
      price
      inventoryQuantity
      barcode
      selectedOptions { name value }
    }
  }
  images(first: 20) {
    nodes { id url }
  }
"""

# App Home list/workbench — skip description + extra images (large catalogs).
PRODUCT_LIST_FIELDS = """
  id
  title
  handle
  vendor
  productType
  status
  options { name position }
  variantsCount { count }
  variants(first: 100) {
    nodes {
      id
      sku
      price
      inventoryQuantity
      selectedOptions { name value }
    }
  }
  images(first: 1) {
    nodes { id url }
  }
"""


def numeric_id(gid_or_num: Any) -> str:
    s = str(gid_or_num or "").strip()
    if not s:
        return ""
    if "/" in s:
        return s.rsplit("/", 1)[-1]
    return s


def shop_host(shop_domain: str) -> str:
    s = (shop_domain or "").strip().lower().replace("https://", "").replace("http://", "")
    s = s.split("/")[0]
    if s and not s.endswith(".myshopify.com"):
        s = f"{s}.myshopify.com"
    return s


def graphql(shop_domain: str, access_token: str, query: str, variables: Optional[dict] = None) -> dict:
    payload = graphql_payload(shop_domain, access_token, query, variables)
    if payload.get("errors"):
        logger.warning("Admin GraphQL errors: %s", payload["errors"])
    return payload.get("data") or {}


def graphql_payload(shop_domain: str, access_token: str, query: str, variables: Optional[dict] = None) -> dict:
    host = shop_host(shop_domain)
    url = f"https://{host}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=12, follow_redirects=False) as client:
        resp = client.post(url, headers=headers, json={"query": query, "variables": variables or {}})
        if resp.status_code != 200:
            logger.warning("Admin GraphQL HTTP %s", resp.status_code)
            return {"errors": [{"message": f"HTTP {resp.status_code}"}]}
        return resp.json()


def product_node_to_rest(node: dict) -> dict:
    options = list(node.get("options") or [])
    options.sort(key=lambda o: o.get("position") or 0)
    opt_names = [(o.get("name") or "") for o in options]
    variants_rest = []
    for v in (node.get("variants") or {}).get("nodes") or []:
        sel = {(o.get("name") or "").lower(): (o.get("value") or "") for o in (v.get("selectedOptions") or [])}
        vals = [sel.get(n.lower(), "") for n in opt_names]
        while len(vals) < 3:
            vals.append("")
        title = " / ".join(x for x in vals if x) or (v.get("title") or "")
        variants_rest.append(
            {
                "id": numeric_id(v.get("id")),
                "sku": v.get("sku") or "",
                "price": str(v.get("price") or "0"),
                "compare_at_price": v.get("compareAtPrice"),
                "inventory_quantity": int(v.get("inventoryQuantity") or 0),
                "option1": vals[0],
                "option2": vals[1],
                "option3": vals[2],
                "title": title,
                "barcode": v.get("barcode") or "",
            }
        )
    images = []
    for img in (node.get("images") or {}).get("nodes") or []:
        url = img.get("url") or img.get("src")
        if url:
            images.append({"id": numeric_id(img.get("id")), "src": url})
    tags = node.get("tags") or ""
    if isinstance(tags, list):
        tags = ", ".join(str(t) for t in tags)
    status = str(node.get("status") or "active").lower()
    vc = node.get("variantsCount") or {}
    total_variants = int(vc.get("count") or len(variants_rest) or 0)
    return {
        "id": numeric_id(node.get("id")),
        "title": node.get("title") or "",
        "handle": node.get("handle") or "",
        "vendor": node.get("vendor") or "",
        "product_type": node.get("productType") or "",
        "body_html": node.get("descriptionHtml") or "",
        "tags": tags,
        "status": status,
        "created_at": node.get("createdAt") or "",
        "variants": variants_rest,
        "images": images,
        "options": [{"name": o.get("name"), "position": o.get("position")} for o in options],
        "total_variant_count": total_variants,
    }


def shop_node_to_rest(node: dict) -> dict:
    primary = node.get("primaryDomain") or {}
    url = str(primary.get("url") or "")
    host = urlparse(url).netloc if url else ""
    myshop = node.get("myshopifyDomain") or node.get("myshopify_domain") or ""
    return {
        "name": node.get("name") or "",
        "myshopify_domain": myshop,
        "email": node.get("email") or "",
        "currency": str(node.get("currencyCode") or node.get("currency") or "").strip().upper(),
        "domain": host or myshop,
    }


def policies_to_rest(nodes: list[dict]) -> list[dict]:
    out = []
    for n in nodes or []:
        ptype = str(n.get("type") or "").upper()
        handle = {
            "PRIVACY_POLICY": "privacy-policy",
            "REFUND_POLICY": "refund-policy",
            "SHIPPING_POLICY": "shipping-policy",
            "TERMS_OF_SERVICE": "terms-of-service",
        }.get(ptype, (n.get("handle") or ptype.lower().replace("_", "-")))
        out.append(
            {
                "handle": handle,
                "title": n.get("title") or handle,
                "body": n.get("body") or "",
                "url": n.get("url") or "",
            }
        )
    return out


def fetch_shop(shop_domain: str, access_token: str) -> dict:
    data = graphql(
        shop_domain,
        access_token,
        """
        query ShopSnapshot {
          shop {
            name
            myshopifyDomain
            email
            currencyCode
            primaryDomain { url }
          }
        }
        """,
    )
    return shop_node_to_rest(data.get("shop") or {})


def fetch_policies(shop_domain: str, access_token: str) -> tuple[list[dict], bool]:
    """Return (policies, readable). readable=False on ACCESS_DENIED or hard failure."""
    try:
        payload = graphql_payload(
            shop_domain,
            access_token,
            """
            query ShopPolicies {
              shop {
                shopPolicies { type title body url }
              }
            }
            """,
        )
    except Exception as e:
        logger.warning("shopPolicies GraphQL failed: %s", e)
        return [], False
    errors = payload.get("errors") or []
    if errors:
        logger.warning("Admin GraphQL errors: %s", errors)
        for err in errors:
            ext = err.get("extensions") or {}
            if ext.get("code") == "ACCESS_DENIED":
                return [], False
        return [], False
    shop = (payload.get("data") or {}).get("shop") or {}
    return policies_to_rest(shop.get("shopPolicies") or []), True


def fetch_product(shop_domain: str, access_token: str, product_id: str) -> Optional[dict]:
    pid = numeric_id(product_id)
    if not pid:
        return None
    gid = f"gid://shopify/Product/{pid}"
    try:
        data = graphql(
            shop_domain,
            access_token,
            f"""
            query ProductById($id: ID!) {{
              product(id: $id) {{
                {PRODUCT_FIELDS}
              }}
            }}
            """,
            {"id": gid},
        )
    except Exception as e:
        logger.warning("product GraphQL failed: %s", e)
        return None
    node = data.get("product")
    if not node:
        return None
    return product_node_to_rest(node)


def fetch_products_page(
    shop_domain: str,
    access_token: str,
    limit: int = 50,
    cursor: Optional[str] = None,
    *,
    lite: bool = False,
) -> dict:
    first = max(1, min(int(limit or 50), 100))
    fields = PRODUCT_LIST_FIELDS if lite else PRODUCT_FIELDS
    data = graphql(
        shop_domain,
        access_token,
        f"""
        query ProductsPage($first: Int!, $after: String) {{
          products(first: $first, after: $after) {{
            pageInfo {{ hasNextPage endCursor }}
            edges {{ node {{ {fields} }} }}
          }}
        }}
        """,
        {"first": first, "after": cursor or None},
    )
    conn = data.get("products") or {}
    nodes = [e.get("node") for e in (conn.get("edges") or []) if e.get("node")]
    products = [product_node_to_rest(n) for n in nodes]
    page = conn.get("pageInfo") or {}
    next_cursor = page.get("endCursor") if page.get("hasNextPage") else None
    return {
        "products": products,
        "next_page_info": next_cursor,
        "total_count": len(products),
    }


def fetch_product_image_urls(shop_domain: str, access_token: str, product_id: str) -> list[str]:
    rest = fetch_product(shop_domain, access_token, product_id)
    if not rest:
        return []
    return [img.get("src") for img in (rest.get("images") or []) if img.get("src")]
