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
type PlanId = (typeof PLAN_IDS)[number];

const PLAN_RANK: Record<PlanId, number> = {
  free: 0,
  starter: 1,
  growth: 2,
};

function openShopifyPricing(url: string) {
  // Hosted App Pricing lives outside the embedded iframe.
  if (typeof window !== "undefined" && window.top) {
    window.top.location.href = url;
    return;
  }
  window.location.href = url;
}

function formatPlanDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
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

  const openManageOnShopify = async (busyKey: string) => {
    setBusy(busyKey);
    setMessage("");
    setChargeUrl("");
    try {
      const fromStatus = billing?.pricing_plans_url;
      if (fromStatus) {
        setChargeUrl(fromStatus);
        setMessage(t("billing.approveHint"));
        setMessageTone("info");
        openShopifyPricing(fromStatus);
        return;
      }
      const token = await shopify.idToken();
      const res = await subscribePlan(token, "growth");
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

  const planKey = (
    PLAN_IDS.includes(String(billing?.plan || "free").toLowerCase() as PlanId)
      ? String(billing?.plan || "free").toLowerCase()
      : "free"
  ) as PlanId;
  const currentRank = PLAN_RANK[planKey];
  const expiresLabel =
    formatPlanDate(
      billing?.active_subscription?.current_period_end ||
        billing?.subscription_period_end,
    ) || "";
  const startedLabel =
    formatPlanDate(
      billing?.active_subscription?.created_at ||
        billing?.subscription_started_at,
    ) || "";
  const paidThrough =
    String(billing?.active_subscription?.status || "").toUpperCase() ===
    "CANCELLED";
  const persistBanner = Boolean(
    billing?.active_subscription?.persists_after_reinstall,
  );

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
          <s-text tone="neutral">{t("billing.plans.onePlanNote")}</s-text>

          <s-stack gap="base" direction="inline">
            {PLAN_IDS.map((id) => {
              const isCurrent = planKey === id;
              const paid = id !== "free";
              const rank = PLAN_RANK[id];
              const isUpgrade = paid && !isCurrent && rank > currentRank;
              const isLower = !isCurrent && rank < currentRank;
              const showPeriodOnCard =
                isCurrent &&
                paid &&
                !persistBanner &&
                Boolean(startedLabel || expiresLabel);

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
                      {isCurrent && paid && expiresLabel && !persistBanner ? (
                        <s-badge tone="info">
                          {t("billing.plans.untilBadge", {
                            expires: expiresLabel,
                          })}
                        </s-badge>
                      ) : null}
                    </s-stack>
                    <s-text>{t(`billing.plans.${id}.price`)}</s-text>
                    <s-text>{t(`billing.plans.${id}.quota`)}</s-text>
                    <s-text tone="neutral">
                      {t(`billing.plans.${id}.blurb`)}
                    </s-text>
                    {showPeriodOnCard ? (
                      <s-text tone="neutral">
                        {paidThrough && expiresLabel
                          ? t("billing.plans.periodPaidThrough", {
                              start: startedLabel || "—",
                              expires: expiresLabel,
                            })
                          : t("billing.plans.periodDetail", {
                              start: startedLabel || "—",
                              expires: expiresLabel || "—",
                            })}
                      </s-text>
                    ) : null}
                    {isUpgrade ? (
                      <s-button
                        variant="primary"
                        disabled={busy !== null}
                        onClick={() => void openManageOnShopify(id)}
                      >
                        {busy === id
                          ? t("cta.generating")
                          : id === "starter"
                            ? t("billing.chooseStarter")
                            : t("billing.chooseGrowth")}
                      </s-button>
                    ) : isLower ? (
                      <s-stack gap="small">
                        <s-text tone="neutral">
                          {expiresLabel
                            ? t("billing.plans.lowerPlanHintUntil", {
                                plan: t(`billing.plans.${planKey}.name`),
                                expires: expiresLabel,
                              })
                            : t("billing.plans.lowerPlanHint", {
                                plan: t(`billing.plans.${planKey}.name`),
                              })}
                        </s-text>
                        <s-button
                          variant="secondary"
                          disabled={busy !== null}
                          onClick={() => void openManageOnShopify(`lower-${id}`)}
                        >
                          {busy === `lower-${id}`
                            ? t("cta.generating")
                            : t("billing.manageOnShopify")}
                        </s-button>
                      </s-stack>
                    ) : !paid && !isCurrent ? (
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
