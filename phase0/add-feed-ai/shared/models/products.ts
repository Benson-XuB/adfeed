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
  platform?: string;
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

import { LOCAL_BACKEND_URL } from "../local-backend.js";

// ── Backend URL (never hardcode localhost http — admin is HTTPS) ──
// Local: set LOCAL_BACKEND_URL in shared/local-backend.js to your API tunnel.
// Or set VITE_BACKEND_URL / BACKEND_URL when the bundler injects env.

function resolveBackendUrl(): string {
  if (LOCAL_BACKEND_URL) return String(LOCAL_BACKEND_URL).replace(/\/$/, "");
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

async function sessionToken(): Promise<string | null> {
  // App Home / Admin UI extensions expose this in a few shapes across API versions.
  const api = globalThis as {
    shopify?: {
      idToken?: () => Promise<string>;
      auth?: { idToken?: () => Promise<string | null> };
      sessionToken?: { get?: () => Promise<string> };
    };
  };
  const s = api.shopify;
  if (!s) return null;
  try {
    if (typeof s.idToken === "function") {
      const t = await s.idToken();
      if (t) return t;
    }
    if (typeof s.auth?.idToken === "function") {
      const t = await s.auth.idToken();
      if (t) return t;
    }
    if (typeof s.sessionToken?.get === "function") {
      const t = await s.sessionToken.get();
      if (t) return t;
    }
  } catch {
    /* fall through — fetch may still auto-attach for app domain */
  }
  return null;
}

async function backendFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers || {});
  const token = await sessionToken();
  // Prefer an explicit token when available. If not, leave Authorization unset so
  // App Home can auto-inject for requests to application_url (our tunnel / backend).
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  try {
    return await fetch(`${BACKEND_URL}${path}`, { ...init, headers });
  } catch (e) {
    const why = e instanceof Error ? e.message : String(e);
    throw new Error(
      why === "Failed to fetch"
        ? `Failed to fetch ${path} (backend unreachable or blocked). Check tunnel/API.`
        : why,
    );
  }
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
  featuredImage {
    url
  }
  featuredMedia {
    preview {
      image {
        url
      }
    }
  }
  media(first: 1) {
    nodes {
      preview {
        image {
          url
        }
      }
    }
  }
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

  const image =
    node.featuredImage?.url ||
    node.featuredMedia?.preview?.image?.url ||
    node.media?.nodes?.[0]?.preview?.image?.url ||
    node.images?.edges?.[0]?.node?.url ||
    variants.find((v: ProductVariant) => v.image)?.image;

  return {
    id: gidToId(node.id),
    title: node.title || "Untitled",
    handle: node.handle || "",
    status: node.status || "ACTIVE",
    productType: node.productType || "",
    vendor: node.vendor || "",
    totalInventory: node.totalInventory ?? 0,
    variantCount: variants.length,
    image: image || undefined,
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
      products(first: $first, after: $after, sortKey: UPDATED_AT, reverse: true) {
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

  if (json?.errors?.length) {
    const msg = json.errors.map((e: { message?: string }) => e.message || "GraphQL error").join("; ");
    throw new Error(msg);
  }
  const data = json?.data?.products;
  if (!data) {
    throw new Error("Products query returned no data");
  }
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

export async function subscribePlan(
  plan: "starter" | "growth",
): Promise<{ confirmation_url?: string; plan: string; quota_total: number }> {
  const resp = await backendFetch("/api/app/billing/subscribe", {
    method: "POST",
    body: JSON.stringify({ plan }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    const detail = err.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d?.msg || d).join("; ")
          : err.detail || `Subscribe failed (${resp.status})`;
    throw new Error(msg);
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

export async function bootstrapStore(): Promise<{
  ok: boolean;
  has_access_token: boolean;
  store_id: string;
  shop_domain: string;
  default_currency?: string;
  message?: string;
}> {
  const resp = await backendFetch("/api/app/bootstrap", { method: "POST", body: "{}" });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `Bootstrap failed (${resp.status})`);
  }
  return resp.json();
}

export async function fetchConnection(): Promise<{
  has_access_token: boolean;
  shop_domain: string;
  shop_name?: string;
  default_brand?: string;
  default_currency?: string;
  quota_remaining?: number;
}> {
  const resp = await backendFetch("/api/app/connection");
  if (!resp.ok) throw new Error("Connection status failed");
  return resp.json();
}

export async function checkMarketReady(country: string): Promise<{
  country: string;
  ready: boolean;
  shop_currency?: string;
  expected_currency?: string;
  message?: string;
}> {
  const q = encodeURIComponent(country);
  const resp = await backendFetch(`/api/app/market-ready?country=${q}`);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(typeof err.detail === "string" ? err.detail : "Market check failed");
  }
  return resp.json();
}

export async function updateStoreBrand(
  defaultBrand: string,
): Promise<{ default_brand: string; shop_name?: string }> {
  const resp = await backendFetch("/api/app/store/brand", {
    method: "PATCH",
    body: JSON.stringify({ default_brand: defaultBrand }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(
      typeof err.detail === "string" ? err.detail : "保存广告品牌失败",
    );
  }
  return resp.json();
}

export async function fetchStoreCompliance(
  countries: string[],
): Promise<{
  light: "green" | "yellow" | "red";
  summary?: { pass?: number; warn?: number; fail?: number };
  shop_currency?: string;
  site_url?: string;
  countries?: string[];
  checks?: Array<{
    id: string;
    status: "pass" | "warn" | "fail";
    message: string;
    suggestion?: string;
    fix_admin_path?: string;
  }>;
}> {
  const qs = encodeURIComponent(countries.join(","));
  const resp = await backendFetch(`/api/app/store/compliance?countries=${qs}`);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(typeof err.detail === "string" ? err.detail : "网站合规诊断失败");
  }
  return resp.json();
}

export async function estimateQuota(
  productIds: string[],
  platforms: string[],
  languages: string[],
): Promise<{ estimate: number; quota_remaining: number; affordable: boolean }> {
  const resp = await backendFetch("/api/app/quota/estimate", {
    method: "POST",
    body: JSON.stringify({
      product_ids: productIds,
      platforms,
      languages,
    }),
  });
  if (!resp.ok) {
    return {
      estimate: productIds.length * platforms.length * languages.length,
      quota_remaining: 0,
      affordable: false,
    };
  }
  return resp.json();
}

export async function generateFeed(
  productIds: string[],
  platforms: string[],
  languages: string[],
): Promise<{ job_id: string; status: string; estimate: number }> {
  const resp = await backendFetch("/api/app/generate", {
    method: "POST",
    body: JSON.stringify({
      product_ids: productIds,
      platforms,
      languages,
    }),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    const detail = err.detail;
    if (detail && typeof detail === "object" && detail.message) {
      throw new Error(detail.message);
    }
    throw new Error(typeof detail === "string" ? detail : "Feed 生成失败");
  }

  return resp.json();
}

/** @typedef {{ country: string; code?: string; message?: string; shop_currency?: string; expected_currency?: string }} BlockedCountry */

export async function pollJob(
  jobId: string,
  opts: { intervalMs?: number; timeoutMs?: number } = {},
): Promise<{
  status: string;
  error_msg?: string;
  result?: {
    feeds?: Array<{ platform?: string; country?: string; language?: string; url: string; items?: number }>;
    blocked_countries?: Array<{
      country: string;
      code?: string;
      message?: string;
      shop_currency?: string;
      expected_currency?: string;
    }>;
    quality_report?: {
      total_rows?: number;
      light?: "green" | "yellow" | "red";
      autofixed?: Array<{
        sku?: string;
        rule_id?: string;
        field?: string;
        message?: string;
        suggestion?: string;
        before?: string;
        after?: string;
      }>;
      warnings?: Array<{
        sku?: string;
        rule_id?: string;
        field?: string;
        message?: string;
        suggestion?: string;
        before?: string;
        after?: string;
      }>;
      fatals?: Array<{
        sku?: string;
        rule_id?: string;
        field?: string;
        message?: string;
        suggestion?: string;
        before?: string;
        after?: string;
      }>;
      title_compare?: Array<{ sku?: string; before?: string; after?: string }>;
      checklist?: string[];
      summary?: { autofixed?: number; warnings?: number; fatals?: number };
    };
    message?: string;
  };
}> {
  const intervalMs = opts.intervalMs ?? 1500;
  const timeoutMs = opts.timeoutMs ?? 10 * 60 * 1000;
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const resp = await backendFetch(`/api/app/jobs/${jobId}`);
    if (!resp.ok) throw new Error("Job status failed");
    const data = await resp.json();
    if (data.status === "completed" || data.status === "failed") return data;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("Job timed out");
}

export type FeedStatusPayload = {
  feeds: FeedInfo[];
  quality_report?: {
    total_rows?: number;
    light?: "green" | "yellow" | "red";
    autofixed?: Array<{
      sku?: string;
      rule_id?: string;
      field?: string;
      message?: string;
      suggestion?: string;
      before?: string;
      after?: string;
    }>;
    warnings?: Array<{
      sku?: string;
      rule_id?: string;
      field?: string;
      message?: string;
      suggestion?: string;
      before?: string;
      after?: string;
    }>;
    fatals?: Array<{
      sku?: string;
      rule_id?: string;
      field?: string;
      message?: string;
      suggestion?: string;
      before?: string;
      after?: string;
    }>;
    title_compare?: Array<{ sku?: string; before?: string; after?: string }>;
    checklist?: string[];
    summary?: { autofixed?: number; warnings?: number; fatals?: number };
  } | null;
  last_job?: {
    id?: string;
    languages?: string[];
    platforms?: string[];
    updated_at?: string;
  } | null;
};

export async function getFeedStatus(_shopDomain?: string): Promise<FeedStatusPayload> {
  const resp = await backendFetch("/api/app/feeds");
  if (!resp.ok) return { feeds: [], quality_report: null, last_job: null };
  const data = await resp.json();
  return {
    feeds: data.feeds || [],
    quality_report: data.quality_report ?? null,
    last_job: data.last_job ?? null,
  };
}

export type BulkPatchItem = { sku: string; color?: string; size?: string };

export async function bulkPatchVariantAttrs(
  patches: BulkPatchItem[],
  platforms: string[],
  languages: string[],
  regenerate = true,
): Promise<{
  updated: string[];
  missing: string[];
  feeds?: Array<{ platform?: string; country?: string; language?: string; url: string; items?: number }>;
  quality_report?: {
    total_rows?: number;
    light?: "green" | "yellow" | "red";
    autofixed?: Array<{
      sku?: string;
      rule_id?: string;
      field?: string;
      message?: string;
      suggestion?: string;
      before?: string;
      after?: string;
    }>;
    warnings?: Array<{
      sku?: string;
      rule_id?: string;
      field?: string;
      message?: string;
      suggestion?: string;
      before?: string;
      after?: string;
    }>;
    fatals?: Array<{
      sku?: string;
      rule_id?: string;
      field?: string;
      message?: string;
      suggestion?: string;
      before?: string;
      after?: string;
    }>;
    title_compare?: Array<{ sku?: string; before?: string; after?: string }>;
    checklist?: string[];
    summary?: { autofixed?: number; warnings?: number; fatals?: number };
  };
  blocked_countries?: Array<{
    country: string;
    code?: string;
    message?: string;
  }>;
  message?: string;
}> {
  const resp = await backendFetch("/api/app/quality/bulk_patch", {
    method: "POST",
    body: JSON.stringify({
      patches,
      platforms,
      languages,
      regenerate,
    }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(typeof err.detail === "string" ? err.detail : "批量修正失败");
  }
  return resp.json();
}

export type FeedImageCandidate = {
  url: string;
  risky?: boolean;
  reason?: string;
  tags?: string[];
};

export type FeedImageContext = {
  sku: string;
  product_id?: string;
  shopify_product_id?: string;
  product_title?: string;
  variant_color?: string;
  current_feed_image?: string;
  effective_image?: string;
  recommended_url?: string;
  candidates?: FeedImageCandidate[];
};

export async function fetchFeedImages(sku: string): Promise<FeedImageContext> {
  const q = encodeURIComponent(sku);
  const resp = await backendFetch(`/api/app/feed-images?sku=${q}`);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(typeof err.detail === "string" ? err.detail : "加载商品图片失败");
  }
  return resp.json();
}

export type ImagePatchItem = { sku: string; image_url: string };

export async function patchFeedImage(
  patches: ImagePatchItem[],
  platforms: string[],
  languages: string[],
  regenerate = true,
) {
  const resp = await backendFetch("/api/app/quality/image_patch", {
    method: "POST",
    body: JSON.stringify({
      patches,
      platforms,
      languages,
      regenerate,
    }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(typeof err.detail === "string" ? err.detail : "主图更新失败");
  }
  return resp.json();
}
