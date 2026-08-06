import { gidToId } from "../utils/gid";

export interface ProductVariant {
  id: string;
  sku: string;
  title: string;
  price: string;
  inventory: number;
  image?: string;
}

export interface Product {
  id: string;
  title: string;
  handle: string;
  status: string;
  productType: string;
  vendor: string;
  totalInventory: number;
  variantCount: number;
  image?: string;
  variants: ProductVariant[];
}

export interface FeedInfo {
  country: string;
  url: string;
  csv_url: string;
  item_count: number;
  updated_at: string;
}

export interface BillingStatus {
  store_id: string;
  shop_domain: string;
  shop_name?: string;
  plan: string;
  billing_status: string;
  quota_total: number;
  quota_used: number;
  quota_remaining: number;
  subscription_id?: string | null;
}

// ── Backend URL (never hardcode localhost) ──

function resolveBackendUrl(): string {
  try {
    const env = (import.meta as ImportMeta & { env?: Record<string, string> }).env;
    const fromEnv = env?.VITE_BACKEND_URL || env?.BACKEND_URL;
    if (fromEnv) return fromEnv.replace(/\/$/, "");
  } catch {
    /* ignore */
  }
  return "https://deltfu.com";
}

export const BACKEND_URL = resolveBackendUrl();

async function sessionToken(): Promise<string> {
  const api = (globalThis as { shopify?: { idToken?: () => Promise<string> } }).shopify;
  if (api?.idToken) {
    return api.idToken();
  }
  throw new Error("Shopify session unavailable");
}

async function backendFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await sessionToken();
  const headers = new Headers(init.headers || {});
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(`${BACKEND_URL}${path}`, { ...init, headers });
}

// ── Shopify Admin GraphQL ──

function gqlFetch(query: string, variables?: Record<string, unknown>) {
  return fetch("shopify:admin/api/2026-07/graphql.json", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, variables }),
  }).then((r) => r.json());
}

const PRODUCT_FIELDS = `
  id
  title
  handle
  status
  productType
  vendor
  totalInventory
  variants(first: 100) {
    edges {
      node {
        id
        sku
        title
        price
        inventoryQuantity
        image {
          url
        }
      }
    }
  }
  images(first: 1) {
    edges {
      node {
        url
      }
    }
  }
`;

function parseProduct(node: any): Product {
  const variants = node.variants.edges.map((e: any) => ({
    id: gidToId(e.node.id),
    sku: e.node.sku || "",
    title: e.node.title || "",
    price: e.node.price || "0.00",
    inventory: e.node.inventoryQuantity ?? 0,
    image: e.node.image?.url,
  }));

  return {
    id: gidToId(node.id),
    title: node.title || "Untitled",
    handle: node.handle || "",
    status: node.status || "ACTIVE",
    productType: node.productType || "",
    vendor: node.vendor || "",
    totalInventory: node.totalInventory ?? 0,
    variantCount: variants.length,
    image: node.images?.edges?.[0]?.node?.url,
    variants,
  };
}

export async function fetchProducts(cursor?: string): Promise<{
  products: Product[];
  hasNextPage: boolean;
  endCursor: string | null;
}> {
  const json = await gqlFetch(
    `#graphql
    query Products($first: Int!, $after: String) {
      products(first: $first, after: $after, sortKey: "UPDATED_AT", reverse: true) {
        pageInfo {
          hasNextPage
          endCursor
        }
        edges {
          node {
            ${PRODUCT_FIELDS}
          }
        }
      }
    }`,
    { first: 50, after: cursor || null },
  );

  const data = json.data.products;
  return {
    products: data.edges.map((e: any) => parseProduct(e.node)),
    hasNextPage: data.pageInfo.hasNextPage,
    endCursor: data.pageInfo.endCursor,
  };
}

export async function fetchAllProducts(): Promise<Product[]> {
  let all: Product[] = [];
  let cursor: string | null = null;
  let hasMore = true;

  while (hasMore) {
    const result = await fetchProducts(cursor || undefined);
    all = [...all, ...result.products];
    hasMore = result.hasNextPage;
    cursor = result.endCursor;
  }

  return all;
}

// ── Backend API (session-authenticated) ──

export async function fetchBillingStatus(): Promise<BillingStatus> {
  const resp = await backendFetch("/api/app/billing/status");
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `Billing status failed (${resp.status})`);
  }
  return resp.json();
}

export async function fetchAppProducts(): Promise<{
  products: Array<{
    id: string;
    title: string;
    image_url: string;
    price: number;
    status: string;
  }>;
  count: number;
  source: string;
}> {
  const resp = await backendFetch("/api/app/products");
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `Products failed (${resp.status})`);
  }
  return resp.json();
}

export async function generateFeed(
  productIds: string[],
  countries: string[],
  shopDomain: string,
): Promise<{ feed_url: string; csv_url: string; item_count: number }> {
  // Authenticated generate lands in Task 8 (/api/app/generate). Until then
  // the legacy path returns 410 with a clear migration message.
  const resp = await backendFetch("/api/shopify/feed", {
    method: "POST",
    body: JSON.stringify({
      product_ids: productIds,
      countries,
      shop_domain: shopDomain,
    }),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || "Feed 生成失败");
  }

  return resp.json();
}

export async function getFeedStatus(shopDomain: string): Promise<FeedInfo[]> {
  const resp = await fetch(
    `${BACKEND_URL}/api/shopify/feed/status?shop_domain=${encodeURIComponent(shopDomain)}`,
  );
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.feeds || [];
}
