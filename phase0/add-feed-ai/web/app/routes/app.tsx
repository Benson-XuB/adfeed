import { useEffect, useState } from "react";
import type { HeadersFunction, LoaderFunctionArgs } from "react-router";
import { Outlet, useLoaderData, useRouteError } from "react-router";
import { boundary } from "@shopify/shopify-app-react-router/server";
import { AppProvider } from "@shopify/shopify-app-react-router/react";
import { useAppBridge } from "@shopify/app-bridge-react";

import { authenticate } from "../shopify.server";
import {
  type ActiveSubscription,
  fetchBillingStatus,
  syncBillingPlanHandle,
} from "../lib/adfeed-api";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);

  const backendUrl = (
    process.env.BACKEND_URL ||
    process.env.VITE_BACKEND_URL ||
    ""
  ).replace(/\/$/, "");

  // eslint-disable-next-line no-undef
  return {
    apiKey: process.env.SHOPIFY_API_KEY || "",
    backendUrl,
  };
};

function formatBillingDate(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function PlanHandleSync() {
  const shopify = useAppBridge();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const handle = params.get("plan_handle");
    if (!handle) return;

    let cancelled = false;
    (async () => {
      try {
        const token = await shopify.idToken();
        if (cancelled) return;
        await syncBillingPlanHandle(token, handle);
        params.delete("plan_handle");
        const next = `${window.location.pathname}${params.toString() ? `?${params}` : ""}${window.location.hash}`;
        window.history.replaceState({}, "", next);
      } catch (e) {
        console.warn("plan_handle sync failed", e);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [shopify]);

  return null;
}

/**
 * Shopify App Store review: if a subscription remains active until period end
 * after uninstall/reinstall, show plan details + start + expiration.
 */
function ActiveSubscriptionBanner() {
  const shopify = useAppBridge();
  const [sub, setSub] = useState<ActiveSubscription | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token = await shopify.idToken();
        if (cancelled) return;
        const status = await fetchBillingStatus(token);
        const active = status.active_subscription;
        if (
          active &&
          (active.created_at || active.current_period_end) &&
          (String(active.status || "").toUpperCase() === "ACTIVE" ||
            active.persists_after_reinstall)
        ) {
          setSub(active);
        } else {
          setSub(null);
        }
      } catch (e) {
        console.warn("active subscription banner load failed", e);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [shopify]);

  if (!sub || dismissed) return null;

  const planName = sub.name || "paid plan";
  const start = formatBillingDate(sub.created_at);
  const end = formatBillingDate(sub.current_period_end);
  const cancelled = String(sub.status || "").toUpperCase() === "CANCELLED";

  return (
    <s-banner tone="info" onDismiss={() => setDismissed(true)}>
      <s-stack gap="small">
        <s-text>
          {cancelled ? (
            <>
              Your <s-text type="strong">{planName}</s-text> plan remains available
              until <s-text type="strong">{end}</s-text> (already paid — no new
              charge until then).
            </>
          ) : (
            <>
              Your <s-text type="strong">{planName}</s-text> subscription is still
              active until <s-text type="strong">{end}</s-text>.
            </>
          )}
        </s-text>
        <s-text tone="neutral">
          Plan: {planName} · Started: {start} · Expires: {end}
        </s-text>
      </s-stack>
    </s-banner>
  );
}

export default function App() {
  const { apiKey, backendUrl } = useLoaderData<typeof loader>();

  useEffect(() => {
    if (backendUrl) {
      window.__ADFEED_BACKEND_URL__ = backendUrl;
    }
  }, [backendUrl]);

  if (typeof window !== "undefined" && backendUrl) {
    window.__ADFEED_BACKEND_URL__ = backendUrl;
  }

  return (
    <AppProvider embedded apiKey={apiKey}>
      <PlanHandleSync />
      <s-app-nav>
        <s-link href="/app">Home</s-link>
        <s-link href="/app/plans">Plans</s-link>
      </s-app-nav>
      <ActiveSubscriptionBanner />
      <Outlet />
    </AppProvider>
  );
}

export function ErrorBoundary() {
  return boundary.error(useRouteError());
}

export const headers: HeadersFunction = (headersArgs) => {
  return boundary.headers(headersArgs);
};
