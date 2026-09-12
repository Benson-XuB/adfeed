import { useCallback, useEffect, useMemo, useState } from "react";
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
import {
  PLAN_IDS,
  PLAN_RANK,
  resolveBillingView,
} from "../lib/billing-view";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  return null;
};

function openShopifyPricing(url: string) {
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

  const view = useMemo(() => resolveBillingView(billing), [billing]);

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

  const summaryLine = view
    ? view.mode === "paid_through"
      ? t("billing.summaryPaidThroughQuota", {
          left: String(view.quotaLeft),
          total: String(view.quotaTotal),
        })
      : t("billing.current", {
          plan: t(`billing.plan_${view.currentPlan}`),
          left: String(view.quotaLeft),
          total: String(view.quotaTotal),
        })
    : null;

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
          {summaryLine ? (
            <s-text>{summaryLine}</s-text>
          ) : (
            <s-text>{t("products.loading")}</s-text>
          )}
          <s-text tone="neutral">{t("billing.plans.pageIntro")}</s-text>
          <s-text tone="neutral">{t("billing.plans.howQuota")}</s-text>
          <s-text tone="neutral">{t("billing.plans.onePlanNote")}</s-text>

          <s-stack gap="base" direction="inline">
            {PLAN_IDS.map((id) => {
              if (!view) return null;

              const isCurrent = view.currentPlan === id;
              const isPrevPaidThrough =
                view.mode === "paid_through" && view.previousPlan === id;
              const rank = PLAN_RANK[id];
              const currentRank = PLAN_RANK[view.currentPlan];
              // Upgrades vs display current (free when paid_through)
              const isUpgrade =
                id !== "free" &&
                !isCurrent &&
                !isPrevPaidThrough &&
                rank > currentRank;
              // Soft downgrade only while Shopify ACTIVE paid plan.
              // Never on Free card (that caused Free+Starter dual messaging).
              const isDowngrade =
                view.mode === "active" &&
                !isCurrent &&
                rank < currentRank &&
                id !== "free";

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
                      {isPrevPaidThrough ? (
                        <s-badge tone="info">
                          {t("billing.plans.paidThroughBadgeShort")}
                        </s-badge>
                      ) : null}
                      {view.mode === "active" &&
                      isCurrent &&
                      id !== "free" &&
                      view.expiresLabel ? (
                        <s-badge tone="info">
                          {t("billing.plans.untilBadge", {
                            expires: view.expiresLabel,
                          })}
                        </s-badge>
                      ) : null}
                    </s-stack>
                    <s-text>{t(`billing.plans.${id}.price`)}</s-text>
                    <s-text>{t(`billing.plans.${id}.quota`)}</s-text>
                    <s-text tone="neutral">
                      {t(`billing.plans.${id}.blurb`)}
                    </s-text>
                    {id === "free" &&
                    view.mode === "paid_through" &&
                    isCurrent ? (
                      <s-text tone="neutral">
                        {t("billing.plans.free.paidThroughHint")}
                      </s-text>
                    ) : null}

                    {view.mode === "active" &&
                    isCurrent &&
                    id !== "free" &&
                    (view.startedLabel || view.expiresLabel) ? (
                      <s-text tone="neutral">
                        {t("billing.plans.periodDetail", {
                          start: view.startedLabel || "—",
                          expires: view.expiresLabel || "—",
                        })}
                      </s-text>
                    ) : null}

                    {isPrevPaidThrough ? (
                      <s-button
                        variant="secondary"
                        disabled={busy !== null}
                        onClick={() => void openManageOnShopify(`pt-${id}`)}
                      >
                        {busy === `pt-${id}`
                          ? t("cta.generating")
                          : t("billing.manageOnShopify")}
                      </s-button>
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
                    ) : null}

                    {isDowngrade ? (
                      <s-stack gap="small">
                        <s-text tone="neutral">
                          {view.expiresLabel
                            ? t("billing.plans.lowerPlanHintUntil", {
                                plan: t(
                                  `billing.plans.${view.currentPlan}.name`,
                                ),
                                expires: view.expiresLabel,
                              })
                            : t("billing.plans.lowerPlanHint", {
                                plan: t(
                                  `billing.plans.${view.currentPlan}.name`,
                                ),
                              })}
                        </s-text>
                        <s-button
                          variant="secondary"
                          disabled={busy !== null}
                          onClick={() =>
                            void openManageOnShopify(`lower-${id}`)
                          }
                        >
                          {busy === `lower-${id}`
                            ? t("cta.generating")
                            : t("billing.manageOnShopify")}
                        </s-button>
                      </s-stack>
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
