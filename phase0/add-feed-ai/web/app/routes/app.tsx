import { useEffect, useState } from "react";
import type { HeadersFunction, LoaderFunctionArgs } from "react-router";
import { Outlet, useLoaderData, useRouteError } from "react-router";
import { boundary } from "@shopify/shopify-app-react-router/server";
import { AppProvider } from "@shopify/shopify-app-react-router/react";
import { useAppBridge } from "@shopify/app-bridge-react";

import { authenticate } from "../shopify.server";
import {
  bootstrapStore,
  fetchBillingStatus,
  syncBillingPlanHandle,
} from "../lib/adfeed-api";
import { resolveBillingView } from "../lib/billing-view";
import { t } from "../lib/i18n";

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
 * Review: if paid period remains after uninstall cancel, banner must show
 * plan details + start date + expiration date (header chip is not enough).
 */
function ReinstallPeriodBanner() {
  const shopify = useAppBridge();
  const [banner, setBanner] = useState<{
    planName: string;
    start: string;
    end: string;
  } | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token = await shopify.idToken();
        if (cancelled) return;
        await bootstrapStore(token);
        if (cancelled) return;
        const status = await fetchBillingStatus(token);
        if (cancelled) return;
        const view = resolveBillingView(status);
        // Require all three fields the reviewer listed
        if (
          view?.mode === "paid_through" &&
          view.previousPlan &&
          view.startedLabel &&
          view.expiresLabel
        ) {
          setBanner({
            planName: t(`billing.plans.${view.previousPlan}.name`),
            start: view.startedLabel,
            end: view.expiresLabel,
          });
        } else {
          setBanner(null);
        }
      } catch (e) {
        console.warn("reinstall period banner load failed", e);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [shopify]);

  if (!banner || dismissed) return null;

  return (
    <div style={{ margin: "12px 16px 0" }}>
      <s-banner tone="info" onDismiss={() => setDismissed(true)}>
        <s-stack gap="small">
          <s-text type="strong">{t("billing.reinstallBannerTitle")}</s-text>
          <s-text>{t("billing.reinstallBannerBody")}</s-text>
          <s-text>
            {t("billing.reinstallBannerPlan", { plan: banner.planName })}
          </s-text>
          <s-text>
            {t("billing.reinstallBannerStart", { start: banner.start })}
          </s-text>
          <s-text>
            {t("billing.reinstallBannerEnd", { expires: banner.end })}
          </s-text>
        </s-stack>
      </s-banner>
    </div>
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
      <ReinstallPeriodBanner />
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
