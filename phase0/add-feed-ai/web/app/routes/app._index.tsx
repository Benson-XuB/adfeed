import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { HeadersFunction, LoaderFunctionArgs } from "react-router";
import { useAppBridge } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { boundary } from "@shopify/shopify-app-react-router/server";
import { t } from "../lib/i18n";
import { FeedWorkbench } from "../components/FeedWorkbench";
import {
  GenerateConfirmModal,
  buildGenerateConfirmItems,
} from "../components/GenerateConfirmModal";
import { MarketMultiSelect } from "../components/MarketMultiSelect";
import setupStyles from "../components/FeedWorkbench.module.css";
import { TARGET_MARKETS } from "../lib/markets";
import {
  type AppProduct,
  type BillingStatus,
  type ComplianceCheck,
  type FeedInfo,
  type WorkbenchProduct,
  getBackendUrl,
  bootstrapStore,
  estimateQuota,
  fetchBillingStatus,
  fetchCompatibleMarkets,
  fetchConnection,
  fetchFeedWorkbench,
  fetchStoreCompliance,
  pickLatestFeed,
  generateFeed,
  getFeedStatus,
  pollJob,
  updateStoreBrand,
} from "../lib/adfeed-api";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  return null;
};

/** MVP: Google only — Meta/TikTok generators exist server-side but stay out of merchant UI. */
const PLATFORMS = [{ code: "google", label: "Google" }] as const;
const SHOW_PLATFORM_PICKER = PLATFORMS.length > 1;

const PIPELINE_IDS = ["title", "category", "variant", "id", "image"] as const;

const DEFAULT_WORKBENCH_FEED: FeedInfo = {
  platform: "google",
  country: "US",
  url: "",
  updated_at: "",
};

function pipelineSteps() {
  return PIPELINE_IDS.map((id) => ({
    id,
    label: t(`pipeline.steps.${id}.label`),
    copy: t(`pipeline.steps.${id}.copy`),
  }));
}

export default function Home() {
  const shopify = useAppBridge();
  const [busy, setBusy] = useState(true);
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState<
    "info" | "success" | "warning" | "critical"
  >("info");
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [products, setProducts] = useState<AppProduct[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [platforms, setPlatforms] = useState<Set<string>>(new Set(["google"]));
  const [languages, setLanguages] = useState<Set<string>>(new Set(["US"]));
  const [adBrand, setAdBrand] = useState("");
  const [adBrandConfirmed, setAdBrandConfirmed] = useState(false);
  const [brandEditOpen, setBrandEditOpen] = useState(false);
  const [adBrandSaving, setAdBrandSaving] = useState(false);
  const [feeds, setFeeds] = useState<FeedInfo[]>([]);
  const [estimate, setEstimate] = useState<{
    estimate: number;
    quota_remaining: number;
    affordable: boolean;
  } | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genConfirmOpen, setGenConfirmOpen] = useState(false);
  const [pipelineStep, setPipelineStep] = useState(0);
  const [marketHint, setMarketHint] = useState("");
  const [compatibleMarkets, setCompatibleMarkets] = useState<string[] | null>(
    null,
  );
  const [compliance, setCompliance] = useState<{
    light: string;
    summary?: { pass?: number; warn?: number; fail?: number };
    checks?: ComplianceCheck[];
  } | null>(null);
  const [complianceLoading, setComplianceLoading] = useState(false);
  const [workbenchProducts, setWorkbenchProducts] = useState<
    WorkbenchProduct[]
  >([]);
  const [workbenchSearch, setWorkbenchSearch] = useState("");
  const initialWorkbenchLoaded = useRef(false);

  const showMsg = (
    text: string,
    tone: "info" | "success" | "warning" | "critical" = "info",
  ) => {
    setMessage(text);
    setMessageTone(tone);
  };

  const withToken = useCallback(
    async <T,>(fn: (token: string) => Promise<T>) => {
      // Always mint a fresh App Bridge session JWT (≈60s TTL).
      const token = await shopify.idToken();
      return fn(token);
    },
    [shopify],
  );

  const workbenchFeed = useMemo(() => pickLatestFeed(feeds), [feeds]);
  const workbenchPlatform = (workbenchFeed?.platform || "google").toLowerCase();
  const workbenchCountry = String(workbenchFeed?.country || "US").toUpperCase();

  const workbenchRowsToProducts = useCallback(
    (rows: WorkbenchProduct[]): AppProduct[] =>
      rows.map((p) => ({
        id: p.id,
        title: p.title,
        image_url: p.image_url,
        price: p.price,
        status: p.status,
        need_color: p.need_color,
        need_size: p.need_size,
        product_type: p.product_type,
        variant_count: p.variant_count,
        variant_skus: p.variant_skus,
      })),
    [],
  );

  const loadWorkbench = useCallback(
    async (feedOverride?: FeedInfo | null): Promise<WorkbenchProduct[]> => {
      const target =
        feedOverride ?? pickLatestFeed(feeds) ?? DEFAULT_WORKBENCH_FEED;
      const plat = (target.platform || "google").toLowerCase();
      const country = String(target.country || "US").toUpperCase();
      try {
        const wb = await withToken((token) =>
          fetchFeedWorkbench(token, plat, country),
        );
        const rows = wb.products || [];
        setWorkbenchProducts(rows);
        setProducts(workbenchRowsToProducts(rows));
        if (wb.feed?.exists && wb.feed.url) {
          setFeeds((prev) => {
            const row: FeedInfo = {
              platform: plat,
              country,
              url: wb.feed.url,
              csv_url: wb.feed.csv_url,
              item_count: wb.feed.item_count,
              updated_at: wb.feed.updated_at || "",
            };
            const key = (f: FeedInfo) =>
              `${(f.platform || "google").toLowerCase()}:${String(f.country || "").toUpperCase()}`;
            const targetKey = key(row);
            const idx = prev.findIndex((f) => key(f) === targetKey);
            if (idx >= 0) {
              const next = [...prev];
              next[idx] = { ...prev[idx], ...row };
              return next;
            }
            return [...prev, row];
          });
        }
        return rows;
      } catch {
        setWorkbenchProducts([]);
        setProducts([]);
        return [];
      }
    },
    [withToken, feeds, workbenchRowsToProducts],
  );

  const runCompliance = useCallback(async (countries?: string[]) => {
    const list = countries?.length ? countries : [...languages];
    if (!list.length) return;
    setComplianceLoading(true);
    try {
      const res = await withToken((token) =>
        fetchStoreCompliance(token, list),
      );
      setCompliance(res);
    } catch (e) {
      showMsg(e instanceof Error ? e.message : String(e), "critical");
    } finally {
      setComplianceLoading(false);
    }
  }, [withToken, languages]);

  const refresh = useCallback(async () => {
    setBusy(true);
    const backend = getBackendUrl();
    if (!backend) {
      showMsg(t("msg.apiNotConfigured"), "critical");
      setBusy(false);
      return;
    }
    try {
      await withToken((token) => bootstrapStore(token));
      const compatPromise = withToken((token) => fetchCompatibleMarkets(token));
      const [conn, bill, feedStatus] = await Promise.all([
        withToken((token) => fetchConnection(token)),
        withToken((token) => fetchBillingStatus(token)),
        withToken((token) => getFeedStatus(token)),
      ]);
      const confirmed = (conn.default_brand || "").trim();
      setAdBrand(confirmed || conn.shop_name || "");
      setAdBrandConfirmed(Boolean(confirmed));
      setBilling(bill);
      const loadedFeeds = feedStatus.feeds || [];
      setFeeds(loadedFeeds);
      const latestFeed = pickLatestFeed(loadedFeeds);
      let ready: string[] = ["US"];
      try {
        const compat = await compatPromise;
        ready = compat.ready?.length ? compat.ready : ["US"];
        setCompatibleMarkets(ready);
        setLanguages((prev) => {
          const readySet = new Set(ready);
          const kept = [...prev].filter((c) => readySet.has(c));
          if (kept.length) return new Set(kept);
          const def = compat.default_country || ready[0] || "US";
          if (readySet.has(def)) return new Set([def]);
          return new Set([ready[0] || "US"]);
        });
      } catch (e) {
        console.warn("[markets] compatible-markets failed", e);
        setCompatibleMarkets(ready);
        setLanguages((prev) => (prev.size ? prev : new Set(ready)));
        setMarketHint(
          e instanceof Error ? e.message : String(e),
        );
      }
      const wbRows = await loadWorkbench(latestFeed);
      initialWorkbenchLoaded.current = true;
      if (!selected.size && wbRows.length) {
        setSelected(new Set(wbRows.slice(0, 3).map((p) => p.id)));
      }
      const markets = [...languages];
      if (markets.length) {
        void runCompliance(markets);
      }
    } catch (e) {
      showMsg(e instanceof Error ? e.message : String(e), "critical");
    } finally {
      setBusy(false);
    }
  }, [withToken, selected.size, loadWorkbench, languages, runCompliance]);

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const productIds = useMemo(() => [...selected], [selected]);
  const platformList = useMemo(() => [...platforms], [platforms]);
  const countryList = useMemo(() => [...languages], [languages]);
  const readyMarketOptions = useMemo(() => {
    if (!compatibleMarkets) return null;
    const set = new Set(compatibleMarkets);
    return TARGET_MARKETS.filter((m) => set.has(m.code));
  }, [compatibleMarkets]);

  useEffect(() => {
    if (busy || !initialWorkbenchLoaded.current || !workbenchFeed) return;
    void loadWorkbench(workbenchFeed);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workbenchPlatform, workbenchCountry]);

  useEffect(() => {
    if (busy || !countryList.length) return;
    void runCompliance(countryList);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [countryList.join(",")]);

  useEffect(() => {
    if (!productIds.length || !platformList.length || !countryList.length) {
      setEstimate(null);
      return;
    }
    let cancelled = false;
    void withToken((token) =>
      estimateQuota(token, productIds, platformList, countryList),
    ).then((e) => {
      if (!cancelled) setEstimate(e);
    });
    return () => {
      cancelled = true;
    };
  }, [productIds, platformList, countryList, withToken]);

  const toggleInSet = (
    set: Set<string>,
    code: string,
    setter: (s: Set<string>) => void,
  ) => {
    const next = new Set(set);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    setter(next);
  };

  const toggleMarket = async (code: string) => {
    if (languages.has(code)) {
      if (languages.size <= 1) {
        setMarketHint(t("setup.needOneMarket"));
        return;
      }
      const next = new Set(languages);
      next.delete(code);
      setLanguages(next);
      setMarketHint("");
      return;
    }
    const next = new Set(languages);
    next.add(code);
    setLanguages(next);
    setMarketHint("");
  };

  const saveAdBrand = async () => {
    setAdBrandSaving(true);
    try {
      const res = await withToken((token) =>
        updateStoreBrand(token, adBrand.trim()),
      );
      setAdBrand(res.default_brand || "");
      setAdBrandConfirmed(Boolean((res.default_brand || "").trim()));
      setBrandEditOpen(false);
      showMsg(t("msg.brandSaved", { brand: res.default_brand }), "success");
    } catch (e) {
      showMsg(e instanceof Error ? e.message : String(e), "critical");
    } finally {
      setAdBrandSaving(false);
    }
  };

  const runGenerate = async (
    ids: string[],
    opts?: { merge?: boolean },
  ) => {
    if (!adBrandConfirmed) {
      showMsg(t("msg.needBrand"), "critical");
      return;
    }
    if (!ids.length) {
      showMsg(t("msg.needProduct"), "critical");
      return;
    }
    if (!platformList.length || !countryList.length) {
      showMsg(t("msg.needPlatformMarket"), "critical");
      return;
    }
    setGenerating(true);
    setPipelineStep(0);
    showMsg(t("msg.checking"), "info");
    const steps = pipelineSteps();
    const tick = setInterval(() => {
      setPipelineStep((i) => Math.min(i + 1, steps.length - 1));
    }, 2800);
    try {
      const job = await withToken((token) =>
        generateFeed(token, ids, platformList, countryList, {
          merge: Boolean(opts?.merge),
        }),
      );
      const done = await pollJob(
        () => shopify.idToken(),
        job.job_id,
      );
      if (done.status === "failed") {
        throw new Error(done.error_msg || t("msg.genFailed"));
      }
      const qr = done.result?.quality_report;
      const status = await withToken((token) => getFeedStatus(token));
      const nextFeeds = status.feeds || [];
      setFeeds(nextFeeds);
      setBilling(await withToken((token) => fetchBillingStatus(token)));
      await loadWorkbench(pickLatestFeed(nextFeeds));
      const fatalN = qr?.summary?.fatals || 0;
      const warnN = qr?.summary?.warnings || 0;
      const autoN = qr?.summary?.autofixed || 0;
      if (fatalN) {
        showMsg(t("msg.doneFatal", { fatals: fatalN }), "warning");
      } else if (warnN || autoN) {
        showMsg(t("msg.doneWarn", { auto: autoN, warn: warnN }), "success");
      } else {
        showMsg(
          opts?.merge ? t("msg.doneMergeOk") : t("msg.doneOk"),
          "success",
        );
      }
    } catch (e) {
      showMsg(
        t("msg.genFailedDetail", {
          detail: e instanceof Error ? e.message : String(e),
        }),
        "critical",
      );
    } finally {
      clearInterval(tick);
      setGenerating(false);
    }
  };

  const onGenerate = () => {
    if (!adBrandConfirmed) {
      showMsg(t("msg.needBrand"), "critical");
      return;
    }
    if (!productIds.length) {
      showMsg(t("msg.needProduct"), "critical");
      return;
    }
    if (!platformList.length || !countryList.length) {
      showMsg(t("msg.needPlatformMarket"), "critical");
      return;
    }
    setGenConfirmOpen(true);
  };

  const genConfirmItems = useMemo(
    () => buildGenerateConfirmItems(productIds, workbenchProducts),
    [productIds, workbenchProducts],
  );

  const genFeedExists = Boolean(
    workbenchFeed &&
      ((workbenchFeed.item_count || 0) > 0 || workbenchFeed.url),
  );

  const confirmGenerate = (ids: string[]) => {
    setGenConfirmOpen(false);
    if (!ids.length) {
      showMsg(t("msg.needProduct"), "critical");
      return;
    }
    setSelected(new Set(ids));
    void runGenerate(ids, { merge: genFeedExists });
  };

  const onGenerateOne = (productId: string) =>
    void runGenerate([productId], { merge: true });

  const copyUrl = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      showMsg(t("feeds.copied"), "success");
      setTimeout(() => showMsg(""), 2000);
    } catch {
      showMsg(t("feeds.copyFailed"), "critical");
    }
  };

  const planKey = String(billing?.plan || "free").toLowerCase();
  const affordable = estimate?.affordable !== false;
  const steps = pipelineSteps();

  return (
    <s-page heading={t("welcome")}>
      {billing ? (
        <s-button slot="secondary-actions" variant="tertiary" href="/app/plans">
          {t("billing.headerQuota", {
            plan: t(`billing.plans.${planKey}.name`),
            left: String(billing.quota_remaining),
            total: String(billing.quota_total),
          })}
        </s-button>
      ) : null}
      <s-button
        slot="secondary-actions"
        variant="secondary"
        href="/app/plans"
        disabled={generating}
      >
        {t("billing.plans.open")}
      </s-button>

      {message ? (
        <s-banner
          tone={messageTone}
          onDismiss={() => showMsg("")}
        >
          <s-text>{message}</s-text>
        </s-banner>
      ) : null}

      <GenerateConfirmModal
        open={genConfirmOpen}
        items={genConfirmItems}
        feedExists={genFeedExists}
        busy={generating}
        onCancel={() => setGenConfirmOpen(false)}
        onConfirm={confirmGenerate}
      />

      {generating ? (
        <s-section heading={t("pipeline.heading")}>
          <s-stack gap="small">
            <s-text>
              {steps[pipelineStep]?.copy || t("cta.generating")}
            </s-text>
            <s-stack direction="inline" gap="small">
              {steps.map((s, i) => (
                <s-badge
                  key={s.id}
                  tone={i <= pipelineStep ? "success" : "info"}
                >
                  {s.label}
                </s-badge>
              ))}
            </s-stack>
          </s-stack>
        </s-section>
      ) : null}

      {busy ? (
        <s-section>
          <s-text>{t("products.loading")}</s-text>
        </s-section>
      ) : null}

      {!busy ? (
        <s-section heading={t("workbench.heading")}>
          <FeedWorkbench
            products={
              workbenchProducts.length
                ? workbenchProducts
                : products.map((p) => ({
                    ...p,
                    feed_status: "pending",
                    feed_item_count: 0,
                    needs_attention: Boolean(p.need_color || p.need_size),
                  }))
            }
            selected={selected}
            setSelected={setSelected}
            platform={workbenchPlatform}
            country={workbenchCountry}
            platforms={platformList}
            feed={workbenchFeed}
            feedExists={Boolean(workbenchFeed)}
            compliance={compliance}
            complianceLoading={complianceLoading}
            search={workbenchSearch}
            setSearch={setWorkbenchSearch}
            withToken={withToken}
            copyUrl={copyUrl}
            setupSlot={
              <s-stack gap="small">
                {SHOW_PLATFORM_PICKER ? (
                  <s-stack gap="small">
                    <s-text type="strong">{t("setup.platforms")}</s-text>
                    <div className={setupStyles.setupChipRow}>
                      {PLATFORMS.map((p) => (
                        <s-button
                          key={p.code}
                          variant="secondary"
                          tone={platforms.has(p.code) ? "success" : undefined}
                          onClick={() =>
                            toggleInSet(platforms, p.code, setPlatforms)
                          }
                        >
                          {p.label}
                        </s-button>
                      ))}
                    </div>
                  </s-stack>
                ) : null}
                <s-stack gap="small">
                  <s-text type="strong">{t("setup.markets")}</s-text>
                  <MarketMultiSelect
                    markets={readyMarketOptions}
                    selected={languages}
                    disabled={generating}
                    onToggle={toggleMarket}
                  />
                  {compatibleMarkets?.length === 0 ? (
                    <s-banner tone="warning">
                      <s-text>{t("setup.noCompatibleMarkets")}</s-text>
                    </s-banner>
                  ) : null}
                  {marketHint ? (
                    <s-banner tone="warning">
                      <s-text>{marketHint}</s-text>
                    </s-banner>
                  ) : null}
                </s-stack>
                <s-stack gap="small">
                  {adBrandConfirmed && !brandEditOpen ? (
                    <s-stack
                      direction="inline"
                      gap="small"
                      alignItems="center"
                    >
                      <s-text tone="success">
                        {t("brand.confirmed", { brand: adBrand })}
                      </s-text>
                      <s-button
                        variant="tertiary"
                        onClick={() => setBrandEditOpen(true)}
                      >
                        {t("brand.change")}
                      </s-button>
                    </s-stack>
                  ) : (
                    <s-stack gap="small">
                      <s-text-field
                        label={t("brand.label")}
                        value={adBrand}
                        placeholder={t("brand.placeholder")}
                        onInput={(e: Event) =>
                          setAdBrand(
                            (e.target as HTMLInputElement).value || "",
                          )
                        }
                        disabled={adBrandSaving}
                      />
                      <s-button
                        variant="secondary"
                        disabled={adBrandSaving || !adBrand.trim()}
                        onClick={() => void saveAdBrand()}
                      >
                        {adBrandSaving
                          ? t("brand.saving")
                          : adBrandConfirmed
                            ? t("brand.update")
                            : t("brand.confirm")}
                      </s-button>
                      {!adBrandConfirmed ? (
                        <s-text tone="caution">
                          {t("overview.storeBrandGate")}
                        </s-text>
                      ) : (
                        <s-button
                          variant="tertiary"
                          onClick={() => setBrandEditOpen(false)}
                        >
                          {t("brand.cancelEdit")}
                        </s-button>
                      )}
                    </s-stack>
                  )}
                  {selected.size === 0 ? (
                    <s-text tone="caution">{t("hub.needProducts")}</s-text>
                  ) : null}
                  {billing && !affordable ? (
                    <s-text tone="caution">{t("quota.insufficient")}</s-text>
                  ) : null}
                  <div className={setupStyles.generateCtaRow}>
                    <button
                      type="button"
                      className={setupStyles.generateCtaBtn}
                      onClick={() => void onGenerate()}
                      disabled={
                        generating ||
                        !adBrandConfirmed ||
                        !productIds.length ||
                        !platformList.length ||
                        !countryList.length ||
                        !affordable
                      }
                    >
                      {generating ? t("cta.generating") : t("cta.generate")}
                    </button>
                  </div>
                </s-stack>
              </s-stack>
            }
            onSavedEdits={() => {
              void withToken((token) => getFeedStatus(token)).then((s) => {
                const nextFeeds = s.feeds || [];
                setFeeds(nextFeeds);
                void loadWorkbench(pickLatestFeed(nextFeeds));
              });
            }}
            onMessage={showMsg}
            busy={busy || generating}
            onGenerateOne={onGenerateOne}
          />
        </s-section>
      ) : null}
    </s-page>
  );
}

export const headers: HeadersFunction = (headersArgs) => {
  return boundary.headers(headersArgs);
};
