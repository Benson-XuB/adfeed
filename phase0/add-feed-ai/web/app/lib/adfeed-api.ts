/**
 * Browser client for AdFeed FastAPI (`phase0/adfeed`).
 * Uses App Bridge session JWT as Bearer — same contract as App Home UI extension.
 *
 * Prefer runtime `window.__ADFEED_BACKEND_URL__` (from app loader) so local
 * Cloudflare tunnel rotates don't require a client rebuild.
 */

declare global {
  interface Window {
    __ADFEED_BACKEND_URL__?: string;
  }
}

export function getBackendUrl(): string {
  if (typeof window !== "undefined") {
    const runtime = window.__ADFEED_BACKEND_URL__;
    if (runtime) return String(runtime).replace(/\/$/, "");
  }
  const fromEnv =
    (typeof import.meta !== "undefined" &&
      (import.meta as ImportMeta & { env?: Record<string, string> }).env
        ?.VITE_BACKEND_URL) ||
    "";
  if (fromEnv) return fromEnv.replace(/\/$/, "");
  if (typeof process !== "undefined" && process.env?.BACKEND_URL) {
    return String(process.env.BACKEND_URL).replace(/\/$/, "");
  }
  return "";
}

/** @deprecated use getBackendUrl() — kept for display; may be stale until runtime set */
export const BACKEND_URL = getBackendUrl();

export async function backendFetch(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<Response> {
  const base = getBackendUrl();
  if (!base) {
    throw new Error(
      "BACKEND_URL / VITE_BACKEND_URL is not set. Point it at the FastAPI tunnel.",
    );
  }
  const headers = new Headers(init.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(`${base}${path}`, { ...init, headers });
}

async function jsonOrThrow<T>(res: Response, fallback: string): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = (err as { detail?: unknown }).detail;
    if (typeof detail === "string") throw new Error(detail);
    if (detail && typeof detail === "object" && "message" in detail) {
      throw new Error(String((detail as { message: string }).message));
    }
    throw new Error(fallback + ` (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export async function fetchHealth(): Promise<{ ok: boolean; status: number }> {
  const base = getBackendUrl();
  if (!base) return { ok: false, status: 0 };
  try {
    const res = await fetch(`${base}/api/health`);
    return { ok: res.ok, status: res.status };
  } catch {
    return { ok: false, status: 0 };
  }
}

export type BillingStatus = {
  store_id: string;
  shop_domain: string;
  shop_name?: string;
  plan: string;
  billing_status: string;
  quota_total: number;
  quota_used: number;
  quota_remaining: number;
  subscription_id?: string | null;
};

export type FeedInfo = {
  country: string;
  platform?: string;
  url: string;
  csv_url: string;
  item_count: number;
  updated_at: string;
};

/** Workbench edits the most recently updated durable feed only. */
export function pickLatestFeed(feeds: FeedInfo[]): FeedInfo | null {
  if (!feeds.length) return null;
  return [...feeds].sort((a, b) => {
    const ta = Date.parse(a.updated_at || "") || 0;
    const tb = Date.parse(b.updated_at || "") || 0;
    return tb - ta;
  })[0];
}

export type AppProduct = {
  id: string;
  title: string;
  image_url: string;
  price: number;
  status: string;
  need_color?: boolean;
  need_size?: boolean;
  product_type?: string;
  variant_count?: number;
  variant_skus?: string[];
};

export async function fetchBillingStatus(token: string): Promise<BillingStatus> {
  const res = await backendFetch("/api/app/billing/status", token);
  return jsonOrThrow(res, "Billing status failed");
}

export async function bootstrapStore(token: string): Promise<{
  ok: boolean;
  has_access_token: boolean;
  store_id: string;
  shop_domain: string;
  default_currency?: string;
  message?: string;
}> {
  const res = await backendFetch("/api/app/bootstrap", token, {
    method: "POST",
    body: "{}",
  });
  return jsonOrThrow(res, "Bootstrap failed");
}

export async function fetchConnection(token: string): Promise<{
  has_access_token: boolean;
  shop_domain: string;
  shop_name?: string;
  default_brand?: string;
  default_currency?: string;
  quota_remaining?: number;
}> {
  const res = await backendFetch("/api/app/connection", token);
  return jsonOrThrow(res, "Connection status failed");
}

export async function updateStoreBrand(
  token: string,
  defaultBrand: string,
): Promise<{ default_brand: string; shop_name?: string }> {
  const res = await backendFetch("/api/app/store/brand", token, {
    method: "PATCH",
    body: JSON.stringify({ default_brand: defaultBrand }),
  });
  return jsonOrThrow(res, "Failed to save ad brand");
}

export async function fetchAppProducts(token: string): Promise<{
  products: AppProduct[];
  count: number;
  source: string;
}> {
  const res = await backendFetch("/api/app/products", token);
  return jsonOrThrow(res, "Products failed");
}

export async function estimateQuota(
  token: string,
  productIds: string[],
  platforms: string[],
  languages: string[],
): Promise<{ estimate: number; quota_remaining: number; affordable: boolean }> {
  const res = await backendFetch("/api/app/quota/estimate", token, {
    method: "POST",
    body: JSON.stringify({
      product_ids: productIds,
      platforms,
      languages,
    }),
  });
  if (!res.ok) {
    return {
      estimate: productIds.length * platforms.length * languages.length,
      quota_remaining: 0,
      affordable: false,
    };
  }
  return res.json();
}

export async function generateFeed(
  token: string,
  productIds: string[],
  platforms: string[],
  languages: string[],
  opts?: { merge?: boolean },
): Promise<{ job_id: string; status: string; estimate: number }> {
  const res = await backendFetch("/api/app/generate", token, {
    method: "POST",
    body: JSON.stringify({
      product_ids: productIds,
      platforms,
      languages,
      merge: Boolean(opts?.merge),
    }),
  });
  return jsonOrThrow(res, "Feed generation failed");
}

export async function pollJob(
  tokenOrGetter: string | (() => Promise<string>),
  jobId: string,
  opts: { intervalMs?: number; timeoutMs?: number } = {},
): Promise<{
  status: string;
  error_msg?: string;
  result?: {
    feeds?: Array<{
      platform?: string;
      country?: string;
      language?: string;
      url: string;
      items?: number;
    }>;
    quality_report?: QualityReport;
    message?: string;
  };
}> {
  const intervalMs = opts.intervalMs ?? 1500;
  const timeoutMs = opts.timeoutMs ?? 10 * 60 * 1000;
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const token =
      typeof tokenOrGetter === "function"
        ? await tokenOrGetter()
        : tokenOrGetter;
    const res = await backendFetch(`/api/app/jobs/${jobId}`, token);
    if (!res.ok) throw new Error("Job status failed");
    const data = await res.json();
    if (data.status === "completed" || data.status === "failed") return data;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("Job timed out");
}

export async function getFeedStatus(token: string): Promise<{
  feeds: FeedInfo[];
  last_job?: { id?: string; languages?: string[]; platforms?: string[] } | null;
}> {
  const res = await backendFetch("/api/app/feeds", token);
  if (!res.ok) return { feeds: [], last_job: null };
  const data = await res.json();
  return {
    feeds: data.feeds || [],
    last_job: data.last_job ?? null,
  };
}

export async function subscribePlan(
  token: string,
  plan: "starter" | "growth",
): Promise<{ confirmation_url?: string; plan: string; quota_total: number }> {
  const res = await backendFetch("/api/app/billing/subscribe", token, {
    method: "POST",
    body: JSON.stringify({ plan }),
  });
  return jsonOrThrow(res, "Subscribe failed");
}

export async function checkMarketReady(
  token: string,
  country: string,
): Promise<{
  country: string;
  ready: boolean;
  shop_currency?: string;
  expected_currency?: string;
  message?: string;
}> {
  const q = encodeURIComponent(country);
  const res = await backendFetch(`/api/app/market-ready?country=${q}`, token);
  return jsonOrThrow(res, "Market check failed");
}

export async function fetchCompatibleMarkets(token: string): Promise<{
  ready: string[];
  shop_currency: string;
  markets_source: string;
  candidate_countries: string[];
  default_country: string;
}> {
  const res = await backendFetch("/api/app/compatible-markets", token);
  return jsonOrThrow(res, "Compatible markets failed");
}

export type ComplianceCheck = {
  id: string;
  status: "pass" | "warn" | "unknown";
  message: string;
  suggestion?: string;
  fix_admin_path?: string;
};

export async function fetchStoreCompliance(
  token: string,
  countries: string[],
): Promise<{
  light: "green" | "yellow";
  summary?: { pass?: number; warn?: number; unknown?: number };
  checks?: ComplianceCheck[];
  shop_currency?: string;
}> {
  const qs = encodeURIComponent(countries.join(","));
  const res = await backendFetch(
    `/api/app/store/compliance?countries=${qs}`,
    token,
  );
  return jsonOrThrow(res, "Store compliance check failed");
}

export type BulkPatchItem = { sku: string; color?: string; size?: string };

export type QualityEvent = {
  sku?: string;
  rule_id?: string;
  field?: string;
  message?: string;
  suggestion?: string;
  before?: string;
  after?: string;
};

export type QualityReport = {
  total_rows?: number;
  light?: "green" | "yellow" | "red";
  autofixed?: QualityEvent[];
  warnings?: QualityEvent[];
  fatals?: QualityEvent[];
  summary?: { autofixed?: number; warnings?: number; fatals?: number };
};

export async function bulkPatchVariantAttrs(
  token: string,
  patches: BulkPatchItem[],
  platforms: string[],
  languages: string[],
  regenerate = true,
  shopifyProductId?: string,
): Promise<{
  updated: string[];
  missing: string[];
  feeds?: Array<{
    platform?: string;
    country?: string;
    language?: string;
    url: string;
    items?: number;
  }>;
  quality_report?: QualityReport;
  message?: string;
}> {
  const res = await backendFetch("/api/app/quality/bulk_patch", token, {
    method: "POST",
    body: JSON.stringify({
      patches,
      platforms,
      languages,
      regenerate,
      shopify_product_id: shopifyProductId || undefined,
    }),
  });
  return jsonOrThrow(res, "Bulk variant update failed");
}

export async function patchShopifyVariantAttrs(
  token: string,
  shopifyProductId: string,
  patches: BulkPatchItem[],
): Promise<{
  updated: string[];
  missing: string[];
  errors?: Array<{ sku: string; message: string }>;
  need_color?: boolean;
  need_size?: boolean;
  message?: string;
  partial?: boolean;
  skipped_no_option?: boolean;
}> {
  const res = await backendFetch("/api/app/products/shopify_variant_patch", token, {
    method: "POST",
    body: JSON.stringify({
      shopify_product_id: shopifyProductId,
      patches,
    }),
  });
  return jsonOrThrow(res, "Shopify write failed");
}

export type FeedPreviewItem = {
  sku: string;
  title: string;
  color: string;
  size: string;
  price: string;
  image_url: string;
  link?: string;
  issue?: string;
};

export type FeedSnapshot = {
  id: string;
  platform: string;
  country: string;
  item_count: number;
  created_at: string;
  download_path?: string;
};

export type FeedImageCandidate = {
  url: string;
  risky?: boolean;
  reason?: string;
  tags?: string[];
};

export async function fetchFeedPreview(
  token: string,
  platform: string,
  country: string,
  opts: { limit?: number; offset?: number; q?: string; productId?: string } = {},
): Promise<{
  items: FeedPreviewItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  url: string;
  csv_url: string;
  item_count: number;
  updated_at?: string;
  product_id?: string | null;
}> {
  const params = new URLSearchParams();
  if (opts.limit != null) params.set("limit", String(opts.limit));
  if (opts.offset != null) params.set("offset", String(opts.offset));
  if (opts.q) params.set("q", opts.q);
  if (opts.productId) params.set("product_id", opts.productId);
  const qs = params.toString();
  const res = await backendFetch(
    `/api/app/feeds/${encodeURIComponent(platform)}/${encodeURIComponent(country)}/preview${qs ? `?${qs}` : ""}`,
    token,
  );
  return jsonOrThrow(res, "Feed preview failed");
}

export type WorkbenchProduct = AppProduct & {
  feed_item_count?: number;
  feed_status?: "ready" | "missing" | "warn" | "pending" | string;
  need_color?: boolean;
  need_size?: boolean;
  need_image?: boolean;
  needs_attention?: boolean;
  variant_skus?: string[];
};

export async function fetchFeedWorkbench(
  token: string,
  platform: string,
  country: string,
): Promise<{
  products: WorkbenchProduct[];
  count: number;
  feed: {
    url: string;
    csv_url: string;
    item_count: number;
    updated_at?: string | null;
    exists: boolean;
  };
  quality_report?: QualityReport | null;
}> {
  const res = await backendFetch(
    `/api/app/feeds/${encodeURIComponent(platform)}/${encodeURIComponent(country)}/workbench`,
    token,
  );
  return jsonOrThrow(res, "Workbench load failed");
}

export async function fetchFeedSnapshots(
  token: string,
  platform: string,
  country: string,
): Promise<{ snapshots: FeedSnapshot[] }> {
  const res = await backendFetch(
    `/api/app/feeds/${encodeURIComponent(platform)}/${encodeURIComponent(country)}/snapshots`,
    token,
  );
  return jsonOrThrow(res, "Snapshot list failed");
}

export async function restoreFeedSnapshot(
  token: string,
  snapshotId: string,
): Promise<{ ok: boolean; url?: string; item_count?: number }> {
  const res = await backendFetch(
    `/api/app/feeds/snapshots/${encodeURIComponent(snapshotId)}/restore`,
    token,
    { method: "POST", body: "{}" },
  );
  return jsonOrThrow(res, "Snapshot restore failed");
}

export async function patchFeedRows(
  token: string,
  patches: Array<{
    sku: string;
    title?: string;
    color?: string;
    size?: string;
    image_url?: string;
  }>,
  platforms: string[],
  languages: string[],
  regenerate = true,
): Promise<{
  updated: string[];
  missing: string[];
  invalid?: string[];
  feeds?: Array<{
    platform?: string;
    country?: string;
    language?: string;
    url: string;
    items?: number;
  }>;
  quality_report?: QualityReport;
  message?: string;
}> {
  const res = await backendFetch("/api/app/feeds/row_patch", token, {
    method: "POST",
    body: JSON.stringify({ patches, platforms, languages, regenerate }),
  });
  return jsonOrThrow(res, "Row edit failed");
}

export async function deleteFeedRows(
  token: string,
  skus: string[],
  platforms: string[],
  languages: string[],
): Promise<{
  ok: boolean;
  removed: string[];
  not_found?: string[];
  item_count?: number;
  url?: string;
  message?: string;
}> {
  const res = await backendFetch("/api/app/feeds/row_delete", token, {
    method: "POST",
    body: JSON.stringify({ skus, platforms, languages }),
  });
  return jsonOrThrow(res, "Row delete failed");
}

export async function fetchFeedImageCandidates(
  token: string,
  sku: string,
): Promise<{
  sku: string;
  current?: string;
  recommended?: string;
  candidates: FeedImageCandidate[];
}> {
  const res = await backendFetch(
    `/api/app/feed-images?sku=${encodeURIComponent(sku)}`,
    token,
  );
  return jsonOrThrow(res, "Image picker failed");
}

export function feedDownloadCsvUrl(platform: string, country: string): string {
  const base = getBackendUrl();
  return `${base}/api/app/feeds/${encodeURIComponent(platform)}/${encodeURIComponent(country)}/download.csv`;
}

export function feedPublicFileUrl(storeRelativeOrAbsolute: string): string {
  if (storeRelativeOrAbsolute.startsWith("http")) return storeRelativeOrAbsolute;
  const base = getBackendUrl();
  return `${base}${storeRelativeOrAbsolute.startsWith("/") ? "" : "/"}${storeRelativeOrAbsolute}`;
}

export type GoogleMerchant = {
  merchant_id: string;
  display_name?: string;
  is_selected?: number;
};

export type GoogleStatus = {
  oauth_configured: boolean;
  connected: boolean;
  scopes: string;
  has_content_scope: boolean;
  has_ads_scope: boolean;
  merchants: GoogleMerchant[];
  selected_merchant_id: string | null;
};

export type GmcIssueRow = {
  id?: string;
  offer_id: string;
  product_id_internal?: string | null;
  status: string;
  reason_code?: string;
  reason_text?: string;
  suggested_action?: string;
};

export async function fetchGoogleStatus(token: string): Promise<GoogleStatus> {
  const res = await backendFetch("/api/app/google/status", token);
  return jsonOrThrow(res, "Google status failed");
}

export async function fetchGoogleIssues(
  token: string,
  merchantId: string,
): Promise<{
  merchant_id: string | null;
  issues: GmcIssueRow[];
  matched: number;
  unmatched: number;
}> {
  const q = merchantId
    ? `?merchant_id=${encodeURIComponent(merchantId)}`
    : "";
  const res = await backendFetch(`/api/app/google/issues${q}`, token);
  return jsonOrThrow(res, "Google issues failed");
}

export async function selectGoogleMerchant(
  token: string,
  merchantId: string,
  displayName = "",
): Promise<void> {
  const res = await backendFetch("/api/app/google/merchants/select", token, {
    method: "POST",
    body: JSON.stringify({
      merchant_id: merchantId,
      display_name: displayName,
    }),
  });
  await jsonOrThrow(res, "Select merchant failed");
}

/** Branch/dev: sync with injectable mock_issues (live Merchant client later). */
export async function syncGoogleIssuesMock(
  token: string,
  merchantId: string,
  mockIssues: Record<string, unknown>[],
): Promise<{ written: number; matched: number; unmatched: number }> {
  const res = await backendFetch("/api/app/google/issues/sync", token, {
    method: "POST",
    body: JSON.stringify({
      merchant_id: merchantId,
      mock_issues: mockIssues,
    }),
  });
  return jsonOrThrow(res, "Issues sync failed");
}
