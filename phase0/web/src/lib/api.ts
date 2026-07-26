const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FetchOptions extends RequestInit {
  token?: string;
}

export async function api<T = unknown>(path: string, options: FetchOptions = {}): Promise<T> {
  const { token, ...fetchOpts } = options;
  const headers: Record<string, string> = {
    ...(fetchOpts.headers as Record<string, string> || {}),
  };

  if (!(fetchOpts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...fetchOpts,
    headers,
    credentials: "include",
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  if (res.headers.get("content-type")?.includes("application/xml")) {
    return res.text() as unknown as T;
  }
  return res.json();
}

// ── Auth ──

export interface User {
  id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
  plan: string;
  quota_total: number;
  quota_used: number;
  quota_remaining: number;
}

export async function getMe(token: string): Promise<User> {
  return api<User>("/api/auth/me", { token });
}

export async function getGoogleUrl(): Promise<string> {
  const { url } = await api<{ url: string }>("/api/auth/google/url");
  return url;
}

export async function googleCallback(code: string): Promise<{ token: string; user: User }> {
  return api("/api/auth/google/callback", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export async function requestMagicLink(email: string): Promise<void> {
  await api("/api/auth/magic-link", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function verifyMagicLink(token: string): Promise<{ token: string; user: User }> {
  return api(`/api/auth/magic-link/verify?token=${encodeURIComponent(token)}`);
}

// ── Upload ──

export interface UploadPreview {
  job_id: string;
  filename: string;
  total_rows: number;
  preview_rows: Record<string, string>[];
  countries: string[];
  quota_remaining: number;
  quota_total: number;
  will_truncate: boolean;
  processable_rows: number;
}

export async function uploadFile(
  file: File,
  countries: string[],
  token: string,
  onProgress?: (pct: number) => void
): Promise<UploadPreview> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("countries", JSON.stringify(countries));

  // 用 XMLHttpRequest 替代 fetch 以获得上传进度
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/upload`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.withCredentials = true;

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      try {
        const data = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(data);
        } else {
          reject(new Error(data.detail || `HTTP ${xhr.status}`));
        }
      } catch {
        reject(new Error("Invalid response"));
      }
    });

    xhr.addEventListener("error", () => reject(new Error("Upload failed")));
    xhr.send(fd);
  });
}

// ── Jobs ──

export interface JobSummary {
  id: string;
  filename: string;
  status: string;
  total_rows: number;
  done_rows: number;
  ok_rows: number;
  fail_rows: number;
  progress_pct: number;
  truncated: boolean;
  created_at: string;
}

export interface JobDetail extends JobSummary {
  preview_rows: Record<string, string>[];
  result_csv: string | null;
  error_msg: string | null;
  updated_at: string;
}

export async function listJobs(token: string): Promise<JobSummary[]> {
  return api("/api/jobs", { token });
}

export async function getJob(id: string, token: string): Promise<JobDetail> {
  return api(`/api/jobs/${id}`, { token });
}

export async function processJob(id: string, token: string): Promise<void> {
  await api(`/api/jobs/${id}/process`, { method: "POST", token });
}

export interface JobResults {
  rows: Record<string, string>[];
  source: string;
  total?: number;
  message?: string;
}

export async function getJobResults(id: string, token: string): Promise<JobResults> {
  return api(`/api/jobs/${id}/results`, { token });
}

// ── Feeds ──

export interface FeedInfo {
  country: string;
  size_bytes: number;
  updated_at: string;
  download_url: string;
}

export async function listFeeds(token: string): Promise<{ feeds: FeedInfo[] }> {
  return api("/api/feeds", { token });
}

export async function downloadFeed(country: string, token: string): Promise<string> {
  return api<string>(`/api/feeds/${country}`, { token });
}

// ── Billing (PayPal) ──

export interface PayPalPlan {
  id: string;
  name: string;
  skus: number;
}

export interface PayPalConfig {
  client_id: string;
  current_plan: string;
  plans: Record<string, PayPalPlan>;
}

export async function getBillingPlans(token: string): Promise<PayPalConfig> {
  return api("/api/billing/plans", { token });
}

export async function activateSubscription(
  paypalSubscriptionId: string,
  paypalPlanId: string,
  token: string
): Promise<void> {
  await api("/api/billing/activate", {
    method: "POST",
    token,
    body: JSON.stringify({
      paypal_subscription_id: paypalSubscriptionId,
      paypal_plan_id: paypalPlanId,
    }),
  });
}
