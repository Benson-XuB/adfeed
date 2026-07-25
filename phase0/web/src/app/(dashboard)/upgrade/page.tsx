"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getBillingPlans, activateSubscription, PayPalPlan } from "@/lib/api";
import Link from "next/link";

declare global {
  interface Window {
    paypal?: {
      Buttons: (options: Record<string, unknown>) => { render: (el: string) => void };
    };
  }
}

const PLAN_LABELS: Record<string, string> = {
  starter: "Starter",
  growth: "Growth",
};
const PLAN_PRICES: Record<string, string> = {
  starter: "$29/mo",
  growth: "$59/mo",
};
const PLAN_DESCS: Record<string, string> = {
  starter: "For solo dropshippers testing new products.",
  growth: "For growing stores with multiple suppliers.",
};

export default function UpgradePage() {
  const { token, user, refresh } = useAuth();
  const [clientId, setClientId] = useState("");
  const [plans, setPlans] = useState<Record<string, PayPalPlan>>({});
  const [loading, setLoading] = useState(true);
  const [activating, setActivating] = useState(false);
  const [activated, setActivated] = useState(false);
  const [error, setError] = useState("");
  const paypalLoaded = useRef(false);

  // 1. 加载 PayPal 配置
  useEffect(() => {
    if (!token) return;
    getBillingPlans(token)
      .then((cfg) => {
        setClientId(cfg.client_id);
        setPlans(cfg.plans);
      })
      .catch(() => setError("Failed to load billing config"))
      .finally(() => setLoading(false));
  }, [token]);

  // 2. 加载 PayPal SDK（只加载一次）
  useEffect(() => {
    if (!clientId || paypalLoaded.current) return;
    paypalLoaded.current = true;

    const script = document.createElement("script");
    script.src = `https://www.paypal.com/sdk/js?client-id=${clientId}&vault=true&intent=subscription`;
    script.async = true;
    script.onload = () => {
      setPlans((prev) => ({ ...prev })); // 强制重渲染
    };
    document.body.appendChild(script);
  }, [clientId]);

  // 3. 渲染 PayPal 按钮（每个 plan 一个按钮）
  useEffect(() => {
    if (!window.paypal || !Object.keys(plans).length) return;

    Object.entries(plans).forEach(([planKey, plan]) => {
      const containerId = `paypal-button-${planKey}`;
      const el = document.getElementById(containerId);
      if (!el) return;
      el.innerHTML = "";

      window.paypal!
        .Buttons({
          style: { shape: "rect", color: "gold", layout: "vertical", label: "subscribe" },
          createSubscription(_data: unknown, actions: unknown) {
            return (actions as { subscription: { create: (opts: { plan_id: string }) => Promise<string> } }).subscription.create({ plan_id: plan.id });
          },
          async onApprove(data: { subscriptionID?: string }) {
            setActivating(true);
            setError("");
            try {
              await activateSubscription(data.subscriptionID!, plan.id, token!);
              setActivated(true);
              refresh();
            } catch (err) {
              setError(err instanceof Error ? err.message : "Activation failed.");
            }
            setActivating(false);
          },
          onError(err: unknown) {
            console.error("PayPal error:", err);
            setError("PayPal error. Please try again.");
          },
        })
        .render(`#${containerId}`);
    });
  }, [plans, token, refresh]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-6 h-6 border-2 border-stone-800 border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-black tracking-tight mb-2">Upgrade</h1>
      <p className="text-sm text-stone-500 mb-8">
        Current plan: <span className="font-bold text-stone-800 uppercase">{user?.plan}</span>
        {" · "}{user?.quota_remaining} SKUs remaining
      </p>

      {activated && (
        <div className="card border-green-200 bg-green-50 mb-6">
          <div className="font-bold text-green-700 mb-1">Subscription activated!</div>
          <p className="text-sm text-green-600">
            Your plan has been upgraded.{" "}
            <Link href="/upload" className="underline font-bold">Start uploading.</Link>
          </p>
        </div>
      )}

      {error && (
        <div className="card border-red-200 bg-red-50 mb-6">
          <div className="text-sm text-red-700">{error}</div>
        </div>
      )}

      {activating && (
        <div className="card border-stone-200 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-5 h-5 border-2 border-stone-800 border-t-transparent animate-spin" />
            <span className="text-sm text-stone-600">Activating your subscription...</span>
          </div>
        </div>
      )}

      {!clientId ? (
        <div className="card text-center text-sm text-stone-400 py-12">
          Payment configuration not found.
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-6 max-w-2xl">
          {Object.entries(plans).map(([planKey, plan]) => {
            const isCurrent = user?.plan === planKey;
            return (
              <div key={planKey} className="card">
                <div className="text-xs text-stone-400 tracking-widest mb-2">
                  {PLAN_LABELS[planKey] || plan.name}
                </div>
                <div className="text-3xl font-black mb-1">
                  {PLAN_PRICES[planKey]}
                </div>
                <div className="text-sm text-stone-500 mb-3">{plan.skus} SKUs / month</div>
                <p className="text-xs text-stone-400 leading-relaxed mb-5">
                  {PLAN_DESCS[planKey] || ""}
                </p>

                {isCurrent ? (
                  <div className="text-xs font-bold text-stone-400 py-3 text-center border border-stone-200">
                    Current plan
                  </div>
                ) : (
                  <div id={`paypal-button-${planKey}`} className="min-h-[45px]" />
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="card mt-6 text-sm text-stone-500">
        <strong className="text-stone-800">What happens next:</strong> Your plan activates
        instantly after payment. Cancel anytime from your PayPal account.
      </div>
    </div>
  );
}
