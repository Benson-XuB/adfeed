/**
 * Single billing display model for Home + Plans.
 *
 * free          — no paid entitlement
 * active        — Shopify ACTIVE paid plan (Current on that plan)
 * paid_through  — uninstall cancelled; no active plan; previous paid period
 *                 still open (banner + keep quota; Free is Current)
 */
import type { BillingStatus } from "./adfeed-api";

export type BillingMode = "free" | "active" | "paid_through";
export type PlanId = "free" | "starter" | "growth";

export const PLAN_IDS: PlanId[] = ["free", "starter", "growth"];
export const PLAN_RANK: Record<PlanId, number> = {
  free: 0,
  starter: 1,
  growth: 2,
};

function asPlanId(raw: string | null | undefined): PlanId {
  const k = String(raw || "free").toLowerCase();
  if (k === "starter" || k === "growth" || k === "free") return k;
  if (k.includes("growth")) return "growth";
  if (k.includes("starter")) return "starter";
  return "free";
}

export function formatBillingDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatBillingDateShort(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export type BillingView = {
  mode: BillingMode;
  /** Plan shown as Current (never a paid plan in paid_through). */
  currentPlan: PlanId;
  /** Previous paid plan when paid_through. */
  previousPlan: PlanId | null;
  startedLabel: string;
  expiresLabel: string;
  expiresShort: string;
  quotaLeft: number;
  quotaTotal: number;
};

export function resolveBillingView(billing: BillingStatus | null): BillingView | null {
  if (!billing) return null;

  const sub = billing.active_subscription;
  const periodEnd =
    sub?.current_period_end || billing.subscription_period_end || "";
  const periodStart =
    sub?.created_at || billing.subscription_started_at || "";

  const paidThrough =
    Boolean(sub?.persists_after_reinstall) ||
    billing.billing_mode === "paid_through" ||
    (String(billing.billing_status || "").toLowerCase() === "cancelled" &&
      Boolean(billing.previous_plan) &&
      Boolean(periodEnd));

  const previousPlan = asPlanId(
    billing.previous_plan || sub?.name || "",
  );
  const previousPlanOk =
    previousPlan === "starter" || previousPlan === "growth"
      ? previousPlan
      : null;

  if (paidThrough) {
    return {
      mode: "paid_through",
      currentPlan: "free",
      previousPlan: previousPlanOk,
      startedLabel: formatBillingDate(periodStart),
      expiresLabel: formatBillingDate(periodEnd),
      expiresShort: formatBillingDateShort(periodEnd),
      quotaLeft: Number(billing.quota_remaining) || 0,
      quotaTotal: Number(billing.quota_total) || 0,
    };
  }

  const plan = asPlanId(billing.plan);
  if (plan === "starter" || plan === "growth") {
    return {
      mode: "active",
      currentPlan: plan,
      previousPlan: null,
      startedLabel: formatBillingDate(periodStart),
      expiresLabel: formatBillingDate(periodEnd),
      expiresShort: formatBillingDateShort(periodEnd),
      quotaLeft: Number(billing.quota_remaining) || 0,
      quotaTotal: Number(billing.quota_total) || 0,
    };
  }

  return {
    mode: "free",
    currentPlan: "free",
    previousPlan: null,
    startedLabel: "",
    expiresLabel: "",
    expiresShort: "",
    quotaLeft: Number(billing.quota_remaining) || 0,
    quotaTotal: Number(billing.quota_total) || 0,
  };
}
