import { useCallback, useEffect, useState } from "react";
import type { HeadersFunction, LoaderFunctionArgs } from "react-router";
import { useAppBridge } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { boundary } from "@shopify/shopify-app-react-router/server";
import { t } from "../lib/i18n";
import {
  type BillingStatus,
  fetchBillingStatus,
  subscribePlan,
} from "../lib/adfeed-api";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  return null;
};

const PLAN_IDS = ["free", "starter", "growth"] as const;

function openShopifyPricing(url: string) {
  // Hosted App Pricing lives outside the embedded iframe.
  if (typeof window !== "undefined" && window.top) {
    window.top.location.href = url;
    return;
  }
  window.location.href = url;
}

export default function Plans() {
  const shopify = useAppBridge();
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState<
    "info" | "success" | "warning" | "critical"
  >("info");
  const [busy, setBusy] = useState<string | null>(null);
  const [chargeUrl, setChargeUrl] = useState("");

  const load = useCallback(async () => {
    try {
      const token = await shopify.idToken();
      setBilling(await fetchBillingStatus(token));
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
      setMessageTone("critical");
    }
  }, [shopify]);

  useEffect(() => {
    void load();
  }, [load]);

  const onChoosePlan = async (plan: "starter" | "growth") => {
    setBusy(plan);
    setMessage("");
    setChargeUrl("");
    try {
      // Prefer URL from status (no create-charge); subscribe endpoint also returns hosted URL.
      const fromStatus = billing?.pricing_plans_url;
      if (fromStatus) {
        setChargeUrl(fromStatus);
        setMessage(t("billing.approveHint"));
        setMessageTone("info");
        openShopifyPricing(fromStatus);
        return;
      }
      const token = await shopify.idToken();
      const res = await subscribePlan(token, plan);
      const url = res.confirmation_url || res.pricing_plans_url;
      if (url) {
        setChargeUrl(url);
        setMessage(t("billing.approveHint"));
        setMessageTone("info");
        openShopifyPricing(url);
      } else {
        setMessageTone("critical");
        setMessage(t("billing.subscribeFailed", { detail: "missing pricing URL" }));
      }
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
      setMessageTone("critical");
    } finally {
      setBusy(null);
    }
  };

  const planKey = String(billing?.plan || "free").toLowerCase();

  return (
    <s-page heading={t("billing.plans.pageTitle")}>
      <s-button slot="secondary-actions" variant="secondary" href="/app">
        {t("billing.plans.back")}
      </s-button>

      {message ? (
        <s-banner tone={messageTone} onDismiss={() => setMessage("")}>
          <s-text>{message}</s-text>
        </s-banner>
      ) : null}

      {chargeUrl ? (
        <s-banner tone="info">
          <s-stack gap="small">
            <s-text>{t("billing.approveHint")}</s-text>
            <s-button variant="primary" href={chargeUrl} target="_top">
              {t("billing.approveInShopify")}
            </s-button>
          </s-stack>
        </s-banner>
      ) : null}

      <s-section>
        <s-stack gap="base">
          {billing ? (
            <s-text>
              {t("billing.current", {
                plan: t(`billing.plan_${planKey}`),
                left: String(billing.quota_remaining),
                total: String(billing.quota_total),
              })}
            </s-text>
          ) : (
            <s-text>{t("products.loading")}</s-text>
          )}
          <s-text tone="neutral">{t("billing.plans.pageIntro")}</s-text>
          <s-text tone="neutral">{t("billing.plans.howQuota")}</s-text>

          <s-stack gap="base" direction="inline">
            {PLAN_IDS.map((id) => {
              const isCurrent = planKey === id;
              const paid = id !== "free";
              return (
                <s-box
                  key={id}
                  padding="base"
                  border="base"
                  borderRadius="base"
                >
                  <s-stack gap="small">
                    <s-stack direction="inline" gap="small" alignItems="center">
                      <s-text type="strong">
                        {t(`billing.plans.${id}.name`)}
                      </s-text>
                      {isCurrent ? (
                        <s-badge tone="success">
                          {t("billing.plans.currentBadge")}
                        </s-badge>
                      ) : null}
                    </s-stack>
                    <s-text>{t(`billing.plans.${id}.price`)}</s-text>
                    <s-text>{t(`billing.plans.${id}.quota`)}</s-text>
                    <s-text tone="neutral">
                      {t(`billing.plans.${id}.blurb`)}
                    </s-text>
                    {paid && !isCurrent ? (
                      <s-button
                        variant="primary"
                        disabled={busy !== null}
                        onClick={() =>
                          void onChoosePlan(id as "starter" | "growth")
                        }
                      >
                        {busy === id
                          ? t("cta.generating")
                          : id === "starter"
                            ? t("billing.chooseStarter")
                            : t("billing.chooseGrowth")}
                      </s-button>
                    ) : !paid ? (
                      <s-text tone="neutral">
                        {t("billing.plans.free.blurb")}
                      </s-text>
                    ) : null}
                  </s-stack>
                </s-box>
              );
            })}
          </s-stack>
        </s-stack>
      </s-section>
    </s-page>
  );
}

export const headers: HeadersFunction = (headersArgs) => {
  return boundary.headers(headersArgs);
};
