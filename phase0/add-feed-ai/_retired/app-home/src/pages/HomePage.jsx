import { useState, useEffect, useCallback } from "preact/hooks";
import {
  fetchAllProducts,
  fetchBillingStatus,
  subscribePlan,
  generateFeed,
  getFeedStatus,
  pollJob,
  estimateQuota,
  bootstrapStore,
  fetchConnection,
  checkMarketReady,
  updateStoreBrand,
  bulkPatchVariantAttrs,
  fetchStoreCompliance,
  fetchFeedImages,
  patchFeedImage,
} from "../../../../shared/models/products";
import { t } from "../i18n.js";
import {
  formatComplianceCheck,
  formatQualityEvent,
} from "../event-i18n.js";

/** @typedef {import('../../../../shared/models/products').Product} Product */
/** @typedef {import('../../../../shared/models/products').FeedInfo} FeedInfo */
/** @typedef {import('../../../../shared/models/products').BillingStatus} BillingStatus */

const PLATFORMS = [
  { code: "google", label: "Google" },
  { code: "meta", label: "Meta" },
  { code: "tiktok", label: "TikTok" },
];

const LANGUAGES = [
  { code: "US", label: "US", currency: "USD" },
  { code: "DE", label: "DE", currency: "EUR" },
  { code: "FR", label: "FR", currency: "EUR" },
  { code: "ES", label: "ES", currency: "EUR" },
  { code: "IT", label: "IT", currency: "EUR" },
];

function adminDeepLink(path) {
  if (!path) return "";
  const clean = String(path).replace(/^\//, "");
  return `shopify:admin/${clean}`;
}

/** Open items get a Shopify deep link; done items stay compact (App Home cannot CSS strikethrough). */
function OpenCheckCard({ title, href, onFix, fixLabel }) {
  return (
    <s-box padding="small" border="base" borderRadius="base">
      <s-stack gap="small">
        <s-text fontWeight="semibold" size="small">
          {title}
        </s-text>
        {href ? (
          <s-link href={href}>{fixLabel || t("compliance.fixInShopify")}</s-link>
        ) : onFix ? (
          <s-button variant="secondary" onClick={onFix}>
            {fixLabel || t("compliance.fixInShopify")}
          </s-button>
        ) : null}
      </s-stack>
    </s-box>
  );
}

function complianceLightMeta(key) {
  const k = key === "yellow" || key === "red" ? key : "green";
  return {
    text: t(`compliance.light${k[0].toUpperCase()}${k.slice(1)}`),
    tone: k === "green" ? "success" : k === "yellow" ? "warning" : "critical",
  };
}

function qualityLightMeta(key) {
  const k = key === "yellow" || key === "red" ? key : "green";
  return {
    text: t(`quality.light${k[0].toUpperCase()}${k.slice(1)}`),
    tone: k === "green" ? "success" : k === "yellow" ? "warning" : "critical",
  };
}

const PIPELINE_STEP_IDS = ["title", "category", "variant", "id", "image"];

function pipelineSteps() {
  return PIPELINE_STEP_IDS.map((id) => ({
    id,
    label: t(`pipeline.steps.${id}.label`),
    copy: t(`pipeline.steps.${id}.copy`),
  }));
}

const HIGHLIGHT_RULES = new Set([
  "S01", "C01", "C02", "AD01", "VA01", "VA02", "M01", "M02", "M03", "D01", "D03",
]);

/** @param {{ field?: string, rule_id?: string }} e */
function isHighlightAutofix(e) {
  const field = String(e?.field || "").toLowerCase();
  const rule = String(e?.rule_id || "").toUpperCase();
  if (HIGHLIGHT_RULES.has(rule)) return true;
  if (rule.startsWith("SEN")) return true;
  return field.includes("size") || field.includes("color") || field.includes("adult");
}

/** @param {any} e */
function isSensitiveComplianceEvent(e) {
  const rule = String(e?.rule_id || "").toUpperCase();
  const field = String(e?.field || "").toLowerCase();
  if (rule === "AD01" || rule.startsWith("SEN")) return true;
  return field.includes("adult");
}

/** @param {any} e */
function isMulticolorFallback(e) {
  const after = String(e?.after || "").trim().toLowerCase().replace(/\s+/g, "");
  return after === "multicolor" || after === "multicolour";
}

/** @param {any} e */
function isOneSizeFallback(e) {
  const rule = String(e?.rule_id || "").toUpperCase();
  const after = String(e?.after || "").trim().toLowerCase();
  const before = String(e?.before || "").trim().toLowerCase();
  // Only empty→One Size needs a fix action. Already-OSFA / alias normalize must not nag forever.
  if (rule === "S05") return false;
  if (rule === "S01") return true;
  if (after === "one size" || after === "osfa") return !before;
  return false;
}

/** @param {any[]} events */
function uniqueSkus(events) {
  const out = [];
  const seen = new Set();
  for (const e of events || []) {
    const sku = String(e?.sku || "").trim();
    if (!sku || seen.has(sku)) continue;
    seen.add(sku);
    out.push(sku);
  }
  return out;
}

function productFeedSku(p) {
  const v = (p?.variants || []).find((x) => x?.sku);
  return v?.sku || "";
}

function productSkus(p) {
  return (p?.variants || []).map((x) => String(x?.sku || "").trim()).filter(Boolean);
}

/** @param {any} e */
function merchantTagFromEvent(e) {
  const rule = String(e?.rule_id || "").toUpperCase();
  const field = String(e?.field || "").toLowerCase();
  const after = String(e?.after || "").trim();
  const afterLow = after.toLowerCase();
  if (isMulticolorFallback(e)) {
    return { key: "color-multi", label: t("tags.colorMulti"), tone: "warning" };
  }
  if (isOneSizeFallback(e)) {
    return { key: "size-one", label: t("tags.sizeOne"), tone: "warning" };
  }
  if (field.includes("color") || rule === "C02" || rule === "VA01") {
    const extracted = rule === "C02" || (after && afterLow !== "multicolor");
    return {
      key: `color-${afterLow || rule}`,
      label: after
        ? extracted
          ? t("tags.colorExtracted", { value: after })
          : t("tags.colorAi", { value: after })
        : t("tags.colorDone"),
      tone: "info",
    };
  }
  if (field.includes("size") || rule === "S01" || rule === "VA02") {
    return {
      key: `size-${afterLow || rule}`,
      label: after ? t("tags.sizeExtracted", { value: after }) : t("tags.sizeDone"),
      tone: "info",
    };
  }
  if (rule === "ID01" || field.includes("identifier")) {
    return { key: "id-no-gtin", label: t("tags.noGtin"), tone: "info" };
  }
  if (rule === "AD01" || rule.startsWith("SEN") || field.includes("adult")) {
    return { key: "adult", label: t("tags.adult"), tone: "warning" };
  }
  return null;
}

/** @param {any[]} autofixed */
function buildAiTagIndex(autofixed) {
  /** @type {Map<string, { key: string, label: string, tone: string }[]>} */
  const index = new Map();
  for (const e of autofixed || []) {
    const sku = String(e?.sku || "").trim().toLowerCase();
    if (!sku) continue;
    const tag = merchantTagFromEvent(e);
    if (!tag) continue;
    const list = index.get(sku) || [];
    if (!list.some((t) => t.key === tag.key)) list.push(tag);
    index.set(sku, list);
  }
  return index;
}

function tagsForProduct(p, tagIndex) {
  const seen = new Set();
  const out = [];
  for (const sku of productSkus(p)) {
    for (const tag of tagIndex.get(sku.toLowerCase()) || []) {
      if (seen.has(tag.key)) continue;
      seen.add(tag.key);
      out.push(tag);
    }
  }
  return out.slice(0, 4);
}

function shopifyAdminHref(productId, variantId) {
  const pid = String(productId || "").replace(/\D/g, "") || String(productId || "").trim();
  if (!pid) return "";
  const vid = String(variantId || "").replace(/\D/g, "");
  if (vid) return `shopify:admin/products/${pid}/variants/${vid}`;
  return `shopify:admin/products/${pid}`;
}

/** @param {Product[]} products */
function buildSkuCatalog(products) {
  /** @type {Map<string, { title: string, image?: string, variantTitle?: string, productId?: string, variantId?: string }>} */
  const map = new Map();
  for (const p of products || []) {
    for (const v of p.variants || []) {
      const sku = String(v?.sku || "").trim();
      if (!sku) continue;
      map.set(sku.toLowerCase(), {
        title: p.title || sku,
        image: v.image || p.image,
        variantTitle: v.title || "",
        productId: p.id,
        variantId: v.id || "",
      });
    }
  }
  return map;
}

/** @param {Map<string, { title: string, image?: string, variantTitle?: string, productId?: string, variantId?: string }>} catalog */
function labelForSku(catalog, sku) {
  const meta = catalog.get(String(sku || "").toLowerCase());
  if (!meta) {
    return { title: sku || "—", image: undefined, variantTitle: "", productId: "", variantId: "" };
  }
  const vt = (meta.variantTitle || "").trim();
  const showVt = vt && vt.toLowerCase() !== "default title";
  return {
    title: showVt ? `${meta.title} · ${vt}` : meta.title,
    image: meta.image,
    variantTitle: vt,
    productId: meta.productId || "",
    variantId: meta.variantId || "",
  };
}

/** Technical noise merchants don't need in the primary table */
function isTechNoiseEvent(e) {
  const field = String(e?.field || "").toLowerCase();
  return (
    field.includes("condition") ||
    field.includes("size_system") ||
    field.includes("size_type") ||
    field.includes("identifier_exists") ||
    field.includes("age_group") ||
    field.includes("gender")
  );
}

export default function HomePage() {
  const [products, setProducts] = useState(/** @type {Product[]} */ ([]));
  const [selected, setSelected] = useState(/** @type {Set<string>} */ (new Set()));
  const [platforms, setPlatforms] = useState(/** @type {Set<string>} */ (new Set(["google"])));
  // Default market: US (USD) — merchant must align storefront currency in Shopify
  const [languages, setLanguages] = useState(/** @type {Set<string>} */ (new Set(["US"])));
  const [shopCurrency, setShopCurrency] = useState("");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [pipelineStep, setPipelineStep] = useState(0);
  const [pipelineComplete, setPipelineComplete] = useState(false);
  const [feeds, setFeeds] = useState(/** @type {FeedInfo[]} */ ([]));
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState(/** @type {"success"|"critical"|"info"|"warning"} */ ("info"));
  const showMsg = (msg, tone = "info") => {
    setMessage(msg);
    setMessageTone(tone);
  };
  const [blockedCountries, setBlockedCountries] = useState(
    /** @type {{ country: string, code?: string, message?: string, shop_currency?: string, expected_currency?: string }[]} */ ([]),
  );
  const [qualityReport, setQualityReport] = useState(
    /** @type {{
      light?: string,
      summary?: { autofixed?: number, warnings?: number, fatals?: number },
      autofixed?: any[],
      warnings?: any[],
      fatals?: any[],
      title_compare?: { sku?: string, before?: string, after?: string }[],
      checklist?: string[]
    } | null} */ (null),
  );
  const [showAutofixLog, setShowAutofixLog] = useState(false);
  const [showTechDetails, setShowTechDetails] = useState(false);
  const [pipelineOpen, setPipelineOpen] = useState(true);
  const [filter, setFilter] = useState("");
  const [billing, setBilling] = useState(/** @type {BillingStatus | null} */ (null));
  const [billingBusy, setBillingBusy] = useState(false);
  const [chargeUrl, setChargeUrl] = useState("");
  /** @type {["home" | "plans", Function]} */
  const [view, setView] = useState(/** @type {"home" | "plans"} */ ("home"));
  const [estimate, setEstimate] = useState(0);
  const [fallbackSelected, setFallbackSelected] = useState(/** @type {Set<string>} */ (new Set()));
  const [magicColor, setMagicColor] = useState("Black");
  const [magicSize, setMagicSize] = useState("");
  /** @type {[null | { sku: string, field: "color" | "size", value: string }, Function]} */
  const [inlineAttrEdit, setInlineAttrEdit] = useState(null);
  const [patching, setPatching] = useState(false);
  const [storeCompliance, setStoreCompliance] = useState(
    /** @type {{
      light?: string,
      summary?: { pass?: number, warn?: number, fail?: number },
      checks?: { id?: string, status?: string, message?: string, suggestion?: string }[]
    } | null} */ (null),
  );
  const [complianceLoading, setComplianceLoading] = useState(false);
  const [adBrand, setAdBrand] = useState("");
  const [adBrandConfirmed, setAdBrandConfirmed] = useState(false);
  const [adBrandSaving, setAdBrandSaving] = useState(false);
  const [brandEditOpen, setBrandEditOpen] = useState(false);
  const [imagePickerSku, setImagePickerSku] = useState("");
  const [imagePickerData, setImagePickerData] = useState(
    /** @type {import('../../../../shared/models/products').FeedImageContext | null} */ (null),
  );
  const [imagePickerSelected, setImagePickerSelected] = useState("");
  const [imagePickerLoading, setImagePickerLoading] = useState(false);
  const [imagePickerSaving, setImagePickerSaving] = useState(false);
  /** @type {"all"|string} scope chip: all active, or productType / __uncategorized__ */
  const [scopeType, setScopeType] = useState("all");
  const [setupOpen, setSetupOpen] = useState(true);
  /** App Home has no scroll-box; show 5 rows per page instead. */
  const PRODUCT_PAGE_SIZE = 5;
  const [productListPage, setProductListPage] = useState(0);

  useEffect(() => {
    (async () => {
      try {
        // Exchange session → offline Admin token before anything else
        try {
          const boot = await bootstrapStore();
          if (!boot.has_access_token) {
            showMsg(t("msg.bootIncomplete", { detail: boot.message || "token exchange failed" }), "critical");
          }
          const ccy = (boot.default_currency || "").toUpperCase();
          if (ccy) setShopCurrency(ccy);
        } catch (e) {
          showMsg(t("msg.bootFailed", { detail: e.message || e }), "critical");
        }

        const [all, status, conn] = await Promise.all([
          fetchAllProducts(),
          fetchBillingStatus().catch(() => null),
          fetchConnection().catch(() => null),
        ]);
        setProducts(all);
        if (status) setBilling(status);
        if (conn) {
          const confirmed = (conn.default_brand || "").trim();
          const suggestion = (conn.shop_name || "").trim();
          setAdBrandConfirmed(Boolean(confirmed));
          // Draft: confirmed brand, else suggest shop name for the merchant to confirm
          setAdBrand(confirmed || suggestion);
        }
        const activeIds = new Set(all.filter((p) => p.status === "ACTIVE").map((p) => p.id));
        setSelected(activeIds);
        setLoading(false);
        try {
          const report = await fetchStoreCompliance(["US"]);
          setStoreCompliance(report);
        } catch {
          /* optional — merchant can re-run */
        }
      } catch (e) {
        showMsg(t("msg.loadProductsFailed", { detail: e.message || e }), "critical");
        setLoading(false);
      }
    })();
  }, []);

  const loadFeedStatus = useCallback(async () => {
    try {
      const payload = await getFeedStatus();
      setFeeds(payload.feeds || []);
      // Refresh-safe: restore last job's quality report so "要处理" stays real
      if (payload.quality_report) {
        setQualityReport(payload.quality_report);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadFeedStatus();
  }, [loadFeedStatus]);

  // Live estimate: SKU × platforms × languages
  useEffect(() => {
    const cost = selected.size * platforms.size * languages.size;
    setEstimate(cost);
    if (selected.size === 0) return;
    estimateQuota(Array.from(selected), Array.from(platforms), Array.from(languages))
      .then((r) => setEstimate(r.estimate))
      .catch(() => setEstimate(cost));
  }, [selected, platforms, languages]);

  // toggleAll defined after `filtered` below

  const toggleProduct = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  const [marketChecking, setMarketChecking] = useState("");
  const [marketHint, setMarketHint] = useState("");

  const toggleInSet = (set, code, setter) => {
    const next = new Set(set);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    setter(next);
  };

  const toggleMarket = async (code) => {
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
    setMarketChecking(code);
    try {
      const res = await checkMarketReady(code);
      if (!res.ready) {
        setMarketHint(
          t("setup.marketLocked", {
            country: t(`setup.country.${code}`),
            expected: t(`setup.ccy.${res.expected_currency || "EUR"}`),
          }),
        );
        return;
      }
      const next = new Set(languages);
      next.add(code);
      setLanguages(next);
      setMarketHint("");
    } catch (e) {
      const meta = LANGUAGES.find((m) => m.code === code);
      if (shopCurrency && meta && meta.currency !== shopCurrency) {
        setMarketHint(
          t("setup.marketLocked", {
            country: t(`setup.country.${code}`),
            expected: t(`setup.ccy.${meta.currency}`),
          }),
        );
        return;
      }
      const next = new Set(languages);
      next.add(code);
      setLanguages(next);
      setMarketHint("");
    } finally {
      setMarketChecking("");
    }
  };

  const handleGenerate = async () => {
    if (selected.size === 0) {
      showMsg(t("msg.needProduct"), "critical");
      return;
    }
    if (platforms.size === 0 || languages.size === 0) {
      showMsg(t("msg.needPlatformMarket"), "critical");
      return;
    }
    if (!adBrandConfirmed || !(adBrand || "").trim()) {
      showMsg(t("msg.needBrand"), "critical");
      return;
    }
    if (billing && estimate > billing.quota_remaining) {
      showMsg(t("msg.quotaShort", { need: estimate, left: billing.quota_remaining }), "critical");
      return;
    }

    setGenerating(true);
    setPipelineStep(0);
    setPipelineComplete(false);
    setPipelineOpen(true);
    showMsg("", "info");
    setBlockedCountries([]);
    setQualityReport(null);
    setFeedsPanelOpen(false);

    const steps = pipelineSteps();
    const tick = setInterval(() => {
      setPipelineStep((i) => Math.min(i + 1, steps.length - 1));
    }, 2800);

    try {
      const start = await generateFeed(
        Array.from(selected),
        Array.from(platforms),
        Array.from(languages),
      );
      showMsg(t("msg.checking"), "info");
      const job = await pollJob(start.job_id);
      if (job.status === "failed") {
        throw new Error(job.error_msg || t("msg.genFailed"));
      }
      const urls = job.result?.feeds || [];
      const blocked = job.result?.blocked_countries || [];
      const quality = job.result?.quality_report || null;
      setBlockedCountries(blocked);
      setQualityReport(quality);
      setShowAutofixLog(false);
      setShowTechDetails(false);
      setFallbackSelected(new Set());
      if (urls.length) {
        setPipelineComplete(true);
        setPipelineOpen(false);
      }

      const fatalN = quality?.summary?.fatals || 0;
      const autoN = quality?.summary?.autofixed || 0;
      const warnN = quality?.summary?.warnings || 0;

      if (blocked.length && !urls.length) {
        showMsg(
          t("msg.blockedOnly", { countries: blocked.map((b) => b.country).join(", ") }),
          "critical",
        );
      } else if (urls.length) {
        let doneMsg = fatalN
          ? t("msg.doneFatal", { fatals: fatalN })
          : warnN || autoN
            ? t("msg.doneWarn", { auto: autoN, warn: warnN })
            : t("msg.doneOk");
        if (blocked.length) {
          doneMsg += t("msg.alsoBlocked", { count: blocked.length });
        }
        showMsg(doneMsg, fatalN ? "warning" : "success");
      } else {
        showMsg(job.result?.message || t("msg.noFeed"), "critical");
      }

      if (urls.length) {
        setFeeds(
          urls.map((u) => ({
            country: u.country || u.language,
            platform: u.platform,
            url: u.url,
            csv_url: (u.url || "").replace(".xml", ".csv"),
            item_count: u.items || 0,
            updated_at: new Date().toISOString(),
          })),
        );
      } else if (!blocked.length) {
        await loadFeedStatus();
      }
      const status = await fetchBillingStatus().catch(() => null);
      if (status) setBilling(status);
    } catch (e) {
      setBlockedCountries([]);
      setQualityReport(null);
      showMsg(t("msg.genFailedDetail", { detail: e.message || e }), "critical");
    }

    clearInterval(tick);
    setGenerating(false);
  };

  const toggleFallbackSku = (sku) => {
    const key = String(sku || "").toLowerCase();
    setFallbackSelected((prev) => {
      const next = new Set([...prev].map((s) => String(s || "").toLowerCase()));
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const selectFallbackSkus = (skus) => {
    setFallbackSelected(new Set(skus));
  };

  const selectFallbackSku = (sku) => {
    const key = String(sku || "").toLowerCase();
    if (!key) return;
    setFallbackSelected((prev) => {
      const next = new Set([...prev].map((s) => String(s || "").toLowerCase()));
      next.add(key);
      return next;
    });
  };

  const applyFallbackPatches = async (patches) => {
    if (!patches.length) {
      showMsg(t("msg.needSku"), "warning");
      return;
    }
    const canon = (s) => String(s || "").toLowerCase();
    const orig = new Map();
    for (const p of products) {
      for (const sku of productSkus(p)) orig.set(canon(sku), sku);
    }
    const mapped = patches.map((p) => ({
      ...p,
      sku: orig.get(canon(p.sku)) || p.sku,
    }));
    setPatching(true);
    showMsg("", "info");
    try {
      const result = await bulkPatchVariantAttrs(
        mapped,
        Array.from(platforms),
        Array.from(languages),
        true,
      );
      if (result.quality_report) setQualityReport(result.quality_report);
      setFallbackSelected(new Set());
      const urls = result.feeds || [];
      if (urls.length) {
        setFeeds(
          urls.map((u) => ({
            country: u.country || u.language,
            platform: u.platform,
            url: u.url,
            csv_url: (u.url || "").replace(".xml", ".csv"),
            item_count: u.items || 0,
            updated_at: new Date().toISOString(),
          })),
        );
      }
      const miss = (result.missing || []).length;
      const updatedN = result.updated?.length || 0;
      if (updatedN === 0) {
        showMsg(
          t("msg.patchFailed", {
            detail: miss
              ? t("msg.patchMissing", { count: miss })
              : result.message || "0 updated",
          }),
          "critical",
        );
      } else {
        showMsg(
          t("msg.patchOk", {
            updated: updatedN,
            missing: miss ? t("msg.patchMissing", { count: miss }) : "",
          }),
          "success",
        );
      }
    } catch (e) {
      showMsg(t("msg.patchFailed", { detail: e.message || e }), "critical");
    }
    setPatching(false);
  };

  const openImagePicker = async (sku) => {
    setImagePickerSku(sku);
    setImagePickerData(null);
    setImagePickerSelected("");
    setImagePickerLoading(true);
    try {
      const ctx = await fetchFeedImages(sku);
      setImagePickerData(ctx);
      setImagePickerSelected(ctx.recommended_url || ctx.effective_image || "");
    } catch (e) {
      showMsg(t("msg.imagesLoadFailed", { detail: e.message || e }), "critical");
      setImagePickerSku("");
    }
    setImagePickerLoading(false);
  };

  const closeImagePicker = () => {
    setImagePickerSku("");
    setImagePickerData(null);
    setImagePickerSelected("");
  };

  const saveImagePicker = async () => {
    if (!imagePickerSku || !imagePickerSelected) {
      showMsg(t("msg.needImage"), "warning");
      return;
    }
    setImagePickerSaving(true);
    showMsg("", "info");
    try {
      const result = await patchFeedImage(
        [{ sku: imagePickerSku, image_url: imagePickerSelected }],
        Array.from(platforms),
        Array.from(languages),
        true,
      );
      if (result.quality_report) setQualityReport(result.quality_report);
      const urls = result.feeds || [];
      if (urls.length) {
        setFeeds(
          urls.map((u) => ({
            country: u.country || u.language,
            platform: u.platform,
            url: u.url,
            csv_url: (u.url || "").replace(".xml", ".csv"),
            item_count: u.items || 0,
            updated_at: new Date().toISOString(),
          })),
        );
      }
      showMsg(t("msg.imageSaved", { sku: imagePickerSku }), "success");
      closeImagePicker();
    } catch (e) {
      showMsg(t("msg.imageFailed", { detail: e.message || e }), "critical");
    }
    setImagePickerSaving(false);
  };

  const runStoreCompliance = async () => {
    setComplianceLoading(true);
    showMsg("", "info");
    try {
      const report = await fetchStoreCompliance(Array.from(languages));
      setStoreCompliance(report);
      // Results live in the checklist card — no top banner (wrong place).
    } catch (e) {
      setStoreCompliance(null);
      showMsg(t("msg.complianceFailed", { detail: e.message || e }), "critical");
    }
    setComplianceLoading(false);
  };

  const saveAdBrand = async () => {
    setAdBrandSaving(true);
    showMsg("", "info");
    try {
      const trimmed = adBrand.trim();
      if (!trimmed) {
        showMsg(t("msg.brandEmpty"), "warning");
        setAdBrandSaving(false);
        return;
      }
      const res = await updateStoreBrand(trimmed);
      setAdBrand(res.default_brand || "");
      setAdBrandConfirmed(Boolean((res.default_brand || "").trim()));
      setBrandEditOpen(false);
      showMsg(t("msg.brandSaved", { brand: res.default_brand }), "success");
    } catch (e) {
      showMsg(t("msg.brandFailed", { detail: e.message || e }), "critical");
    }
    setAdBrandSaving(false);
  };

  const typeKey = (p) => {
    const raw = String(p?.productType || "").trim();
    return raw || "__uncategorized__";
  };
  const activeProducts = products.filter((p) => p.status === "ACTIVE");
  const typeCounts = (() => {
    /** @type {Map<string, number>} */
    const m = new Map();
    for (const p of activeProducts) {
      const k = typeKey(p);
      m.set(k, (m.get(k) || 0) + 1);
    }
    return m;
  })();
  // Order: Uncategorized first, then named product types (All is rendered separately).
  const typeChips = Array.from(typeCounts.entries()).sort((a, b) => {
    if (a[0] === "__uncategorized__") return -1;
    if (b[0] === "__uncategorized__") return 1;
    return a[0].localeCompare(b[0]);
  });
  const scopedProducts =
    scopeType === "all" || scopeType === "needs"
      ? activeProducts
      : activeProducts.filter((p) => typeKey(p) === scopeType);
  const filtered = filter
    ? scopedProducts.filter(
        (p) =>
          p.title.toLowerCase().includes(filter.toLowerCase()) ||
          p.productType.toLowerCase().includes(filter.toLowerCase()) ||
          p.vendor.toLowerCase().includes(filter.toLowerCase()),
      )
    : scopedProducts;

  const totalVariants = products.reduce((sum, p) => sum + p.variantCount, 0);
  const quotaPct =
    billing && billing.quota_total > 0
      ? Math.min(100, Math.round((billing.quota_used / billing.quota_total) * 100))
      : 0;
  const affordable = !billing || estimate <= billing.quota_remaining;

  const qualityLightKey = /** @type {"green"|"yellow"|"red"} */ (
    qualityReport?.light === "red" ||
    qualityReport?.light === "yellow" ||
    qualityReport?.light === "green"
      ? qualityReport.light
      : (qualityReport?.summary?.fatals || 0) > 0
        ? "red"
        : (qualityReport?.summary?.autofixed || 0) > 0 ||
            (qualityReport?.summary?.warnings || 0) > 0
          ? "yellow"
          : "green"
  );
  const qualityLight = qualityLightMeta(qualityLightKey);
  const steps = pipelineSteps();
  const autofixedEvents = qualityReport?.autofixed || [];
  const autofixPreview = autofixedEvents.slice(0, 20);
  const missingVariantIdWarns = (qualityReport?.warnings || []).filter(
    (e) => e.rule_id === "VA04",
  );
  const titleCompare = qualityReport?.title_compare || [];
  const highlightRows = autofixedEvents.filter(isHighlightAutofix);
  const techNoiseRows = highlightRows.filter(isTechNoiseEvent);
  const reviewHighlightRows = highlightRows.filter(
    (e) => !isTechNoiseEvent(e) && !isMulticolorFallback(e) && !isOneSizeFallback(e),
  );
  const multicolorSkus = uniqueSkus(autofixedEvents.filter(isMulticolorFallback));
  const oneSizeSkus = uniqueSkus(autofixedEvents.filter(isOneSizeFallback));
  const sensitiveEvents = [
    ...(qualityReport?.fatals || []),
    ...(qualityReport?.warnings || []),
    ...autofixedEvents,
  ].filter(isSensitiveComplianceEvent);
  const imageWarnEvents = (qualityReport?.warnings || []).filter((e) => e.rule_id === "I03");
  const imageWarnSkus = uniqueSkus(imageWarnEvents);
  const skuCanon = (s) => String(s || "").toLowerCase();
  const fallbackSkuSet = new Set(
    [...multicolorSkus, ...oneSizeSkus].map((s) => skuCanon(s)),
  );
  const aiTagIndex = buildAiTagIndex([...autofixedEvents, ...sensitiveEvents]);
  const fallbackSelectedList = Array.from(fallbackSelected)
    .map((s) => skuCanon(s))
    .filter((s) => fallbackSkuSet.has(s));
  const skuCatalog = buildSkuCatalog(products);
  const needsReview =
    multicolorSkus.length > 0 ||
    oneSizeSkus.length > 0 ||
    sensitiveEvents.length > 0 ||
    imageWarnSkus.length > 0;
  const storeGateBrand = !adBrandConfirmed;
  const storeGateCurrency = blockedCountries.length > 0;
  const hasPostGenerate = Boolean(qualityReport) || feeds.length > 0 || pipelineComplete;
  const showSetup = true; // Hub: scope always visible (screenshot flow)
  const storeOpenChecks = (storeCompliance?.checks || []).filter((c) => c.status !== "pass");
  const showStoreTodos =
    hasPostGenerate &&
    !generating &&
    (storeGateBrand || storeGateCurrency || storeOpenChecks.length > 0);

  const colorSet = new Set(multicolorSkus.map((s) => String(s).toLowerCase()));
  const sizeSet = new Set(oneSizeSkus.map((s) => String(s).toLowerCase()));
  const imageSet = new Set(imageWarnSkus.map((s) => String(s).toLowerCase()));
  const wordSet = new Set(uniqueSkus(sensitiveEvents).map((s) => String(s).toLowerCase()));
  const hintsFor = (p) => {
    const skus = productSkus(p);
    const colorSkus = skus.filter((s) => colorSet.has(s.toLowerCase()));
    const sizeSkus = skus.filter((s) => sizeSet.has(s.toLowerCase()));
    const imageSkus = skus.filter((s) => imageSet.has(s.toLowerCase()));
    const wordSkus = skus.filter((s) => wordSet.has(s.toLowerCase()));
    const fixSkus = [...new Set([...colorSkus, ...sizeSkus])];
    return {
      colorSkus,
      sizeSkus,
      imageSkus,
      wordSkus,
      fixSkus,
      has:
        colorSkus.length > 0 ||
        sizeSkus.length > 0 ||
        imageSkus.length > 0 ||
        wordSkus.length > 0,
    };
  };
  const needsProductCount = activeProducts.filter((p) => hintsFor(p).has).length;
  const listedUnsorted =
    scopeType === "needs" ? filtered.filter((p) => hintsFor(p).has) : filtered;
  const listedProducts = [...listedUnsorted].sort((a, b) => {
    const ha = hintsFor(a).has ? 0 : 1;
    const hb = hintsFor(b).has ? 0 : 1;
    return ha - hb;
  });
  const productPageCount = Math.max(1, Math.ceil(listedProducts.length / PRODUCT_PAGE_SIZE));
  const safeProductPage = Math.min(productListPage, productPageCount - 1);
  const pagedProducts = listedProducts.slice(
    safeProductPage * PRODUCT_PAGE_SIZE,
    safeProductPage * PRODUCT_PAGE_SIZE + PRODUCT_PAGE_SIZE,
  );

  useEffect(() => {
    setProductListPage(0);
  }, [scopeType, filter]);

  const toggleAll = () => {
    if (listedProducts.length === 0) return;
    const visibleIds = listedProducts.map((p) => p.id);
    const allVisibleSelected = visibleIds.every((id) => selected.has(id));
    if (allVisibleSelected) {
      const next = new Set(selected);
      for (const id of visibleIds) next.delete(id);
      setSelected(next);
    } else {
      setSelected(new Set([...selected, ...visibleIds]));
    }
  };

  const pickNeedsScope = () => {
    setScopeType("needs");
    const list = activeProducts.filter((p) => hintsFor(p).has);
    setSelected(new Set(list.map((p) => p.id)));
  };

  const fixThisProduct = (p) => {
    const hints = hintsFor(p);
    const skus = hints.fixSkus.map((s) => String(s).toLowerCase());
    if (skus.length === 0) {
      showMsg(t("overview.emptyNeeds"), "info");
      return;
    }
    setInlineAttrEdit(null);
    setFallbackSelected(new Set(skus));
  };

  const startPlanChange = async (plan) => {
    setBillingBusy(true);
    try {
      const res = await subscribePlan(plan);
      if (res.confirmation_url) {
        setChargeUrl(res.confirmation_url);
        showMsg(t("billing.approveHint"), "info");
      } else {
        showMsg(t("billing.subscribeFailed", { detail: "missing confirmation URL" }), "critical");
      }
    } catch (e) {
      showMsg(t("billing.subscribeFailed", { detail: e.message || e }), "critical");
    }
    setBillingBusy(false);
  };

  const openInlineAttrEdit = (skuKey, field) => {
    const key = String(skuKey || "").toLowerCase();
    // Single-row edit only — never open the bulk bar above.
    setFallbackSelected(new Set());
    setInlineAttrEdit({
      sku: key,
      field,
      value: "",
    });
  };

  const saveInlineAttrEdit = async () => {
    if (!inlineAttrEdit) return;
    const value = String(inlineAttrEdit.value || "").trim();
    if (!value) {
      showMsg(t("msg.needSku"), "warning");
      return;
    }
    const patch =
      inlineAttrEdit.field === "size"
        ? { sku: inlineAttrEdit.sku, size: value }
        : { sku: inlineAttrEdit.sku, color: value };
    await applyFallbackPatches([patch]);
    setInlineAttrEdit(null);
  };

  const renderSkuFixLine = (sku, { needColor, needSize }) => {
    const info = labelForSku(skuCatalog, sku);
    const label = info.variantTitle || sku;
    const key = String(sku || "").toLowerCase();
    const href = shopifyAdminHref(info.productId, info.variantId);
    const editing =
      inlineAttrEdit &&
      String(inlineAttrEdit.sku).toLowerCase() === key
        ? inlineAttrEdit
        : null;
    return (
      <s-box key={`fix-${sku}`} padding="small" border="base" borderRadius="base">
        <s-stack gap="small">
          {href ? (
            <s-link href={href}>{label}</s-link>
          ) : (
            <s-text size="small">{label}</s-text>
          )}
          {!editing && (
            <s-stack direction="inline" gap="small">
              {needColor && (
                <s-button
                  variant="secondary"
                  onClick={() => openInlineAttrEdit(key, "color")}
                  disabled={patching}
                >
                  {t("products.fixColorBtn")}
                </s-button>
              )}
              {needSize && (
                <s-button
                  variant="secondary"
                  onClick={() => openInlineAttrEdit(key, "size")}
                  disabled={patching}
                >
                  {t("products.fixSizeBtn")}
                </s-button>
              )}
            </s-stack>
          )}
          {editing && (
            <s-stack gap="small">
              <s-text-field
                label={
                  editing.field === "size" ? t("quality.size") : t("quality.color")
                }
                value={editing.value}
                placeholder={
                  editing.field === "size"
                    ? t("quality.sizePh")
                    : t("quality.colorPh")
                }
                onInput={(e) =>
                  setInlineAttrEdit({
                    ...editing,
                    value: e.target?.value || "",
                  })
                }
                disabled={patching}
              />
              <s-stack direction="inline" gap="small">
                <s-button
                  variant="primary"
                  disabled={patching || !String(editing.value || "").trim()}
                  onClick={saveInlineAttrEdit}
                >
                  {patching
                    ? t("quality.applying")
                    : editing.field === "size"
                      ? t("quality.applySize")
                      : t("quality.applyColor")}
                </s-button>
                <s-button
                  variant="tertiary"
                  disabled={patching}
                  onClick={() => setInlineAttrEdit(null)}
                >
                  {t("brand.cancelEdit")}
                </s-button>
              </s-stack>
            </s-stack>
          )}
        </s-stack>
      </s-box>
    );
  };


  const pickScope = (key) => {
    setScopeType(key);
    const list =
      key === "all"
        ? activeProducts
        : activeProducts.filter((p) => typeKey(p) === key);
    setSelected(new Set(list.map((p) => p.id)));
  };

  const renderBulkEditBar = () =>
    // Bulk bar only for「改全部规格」— never while a single-row editor is open.
    !inlineAttrEdit && fallbackSelectedList.length > 0 ? (
      <s-banner tone="info">
        <s-stack gap="small">
          <s-text fontWeight="semibold">
            {t("quality.bulkTitle", { count: fallbackSelectedList.length })}
          </s-text>
          <s-text size="small" tone="subdued">
            {t("quality.bulkHelp")}
          </s-text>
          <s-stack direction="inline" gap="small" alignItems="end">
            <s-text-field
              label={t("quality.color")}
              value={magicColor}
              placeholder={t("quality.colorPh")}
              onInput={(e) => setMagicColor(e.target?.value || "")}
              disabled={patching}
            />
            <s-button
              variant="primary"
              disabled={patching || !String(magicColor || "").trim()}
              onClick={() =>
                applyFallbackPatches(
                  fallbackSelectedList.map((sku) => ({
                    sku,
                    color: String(magicColor).trim(),
                  })),
                )
              }
            >
              {patching ? t("quality.applying") : t("quality.applyColor")}
            </s-button>
          </s-stack>
          <s-stack direction="inline" gap="small" alignItems="end">
            <s-text-field
              label={t("quality.size")}
              value={magicSize}
              placeholder={t("quality.sizePh")}
              onInput={(e) => setMagicSize(e.target?.value || "")}
              disabled={patching}
            />
            <s-button
              variant="primary"
              disabled={patching || !String(magicSize || "").trim()}
              onClick={() =>
                applyFallbackPatches(
                  fallbackSelectedList.map((sku) => ({
                    sku,
                    size: String(magicSize).trim(),
                  })),
                )
              }
            >
              {t("quality.applySize")}
            </s-button>
            <s-button
              variant="secondary"
              disabled={patching}
              onClick={() =>
                applyFallbackPatches(
                  fallbackSelectedList.map((sku) => ({
                    sku,
                    size: "One Size",
                  })),
                )
              }
            >
              {t("quality.oneSizeBtn")}
            </s-button>
            <s-button variant="tertiary" disabled={patching} onClick={() => setFallbackSelected(new Set())}>
              {t("quality.clearSelection")}
            </s-button>
          </s-stack>
        </s-stack>
      </s-banner>
    ) : null;

  const planKey = String(billing?.plan || "free").toLowerCase();

  const planCards = [
    {
      id: "free",
      price: t("billing.plans.free.price"),
      quota: t("billing.plans.free.quota"),
      blurb: t("billing.plans.free.blurb"),
      paid: false,
    },
    {
      id: "starter",
      price: t("billing.plans.starter.price"),
      quota: t("billing.plans.starter.quota"),
      blurb: t("billing.plans.starter.blurb"),
      paid: true,
    },
    {
      id: "growth",
      price: t("billing.plans.growth.price"),
      quota: t("billing.plans.growth.quota"),
      blurb: t("billing.plans.growth.blurb"),
      paid: true,
    },
  ];

  const chargeBanner = chargeUrl ? (
    <s-banner tone="info">
      <s-stack gap="small">
        <s-text>{t("billing.approveHint")}</s-text>
        <s-button variant="primary" href={chargeUrl}>
          {t("billing.approveInShopify")}
        </s-button>
      </s-stack>
    </s-banner>
  ) : null;

  if (view === "plans") {
    return (
      <s-page heading={t("billing.plans.pageTitle")}>
        <s-button slot="secondary-actions" variant="secondary" onClick={() => setView("home")}>
          {t("billing.plans.back")}
        </s-button>
        {message && (
          <s-banner tone={messageTone}>
            <s-text>{message}</s-text>
          </s-banner>
        )}
        {chargeBanner}
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
            ) : null}
            <s-text tone="subdued">{t("billing.plans.pageIntro")}</s-text>
            <s-text tone="subdued" size="small">
              {t("billing.plans.howQuota")}
            </s-text>
            <s-stack direction="inline" gap="base" style="flex-wrap: wrap; align-items: stretch">
              {planCards.map((card) => {
                const isCurrent = planKey === card.id;
                return (
                  <s-box
                    key={card.id}
                    padding="base"
                    border="base"
                    borderRadius="base"
                    style="min-width: 200px; flex: 1 1 200px"
                  >
                    <s-stack gap="small">
                      <s-stack direction="inline" gap="small" alignItems="center">
                        <s-text fontWeight="semibold">{t(`billing.plans.${card.id}.name`)}</s-text>
                        {isCurrent ? (
                          <s-badge tone="success">{t("billing.plans.currentBadge")}</s-badge>
                        ) : null}
                      </s-stack>
                      <s-text fontWeight="bold">{card.price}</s-text>
                      <s-text>{card.quota}</s-text>
                      <s-text tone="subdued" size="small">
                        {card.blurb}
                      </s-text>
                      {isCurrent ? (
                        <s-button variant="secondary" disabled>
                          {t("billing.plans.currentBadge")}
                        </s-button>
                      ) : card.paid ? (
                        <s-button
                          variant="primary"
                          disabled={billingBusy || generating}
                          onClick={() => startPlanChange(card.id)}
                        >
                          {billingBusy
                            ? t("billing.plans.starting")
                            : t("billing.plans.choose", { plan: t(`billing.plans.${card.id}.name`) })}
                        </s-button>
                      ) : (
                        <s-button variant="secondary" disabled>
                          {t("billing.plans.included")}
                        </s-button>
                      )}
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

  return (
    <s-page heading="广告商品 Feed · v78">
      {billing ? (
        <s-button
          slot="secondary-actions"
          variant="tertiary"
          onClick={() => setView("plans")}
        >
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
        disabled={generating}
        onClick={() => setView("plans")}
      >
        {t("billing.plans.open")}
      </s-button>
      {message && (
        <s-banner tone={messageTone}>
          <s-text>{message}</s-text>
        </s-banner>
      )}
      {chargeBanner}

      {feeds.length > 0 && !generating ? (
        <s-section heading={t("hub.feedsHeading")}>
          <s-box padding="base" border="base" borderRadius="base">
            <s-stack gap="small">
              <s-text tone="subdued" size="small">
                {t("feeds.help")}
              </s-text>
              <s-grid gridTemplateColumns="1fr 1fr" gap="base">
                {feeds.map((f) => {
                  const code = String(f.country || "").toUpperCase();
                  const meta = LANGUAGES.find((m) => m.code === code);
                  const ccy = meta?.currency || "";
                  const synced = Number(f.item_count) > 0;
                  return (
                    <s-box
                      key={`${f.platform || "google"}-${code}`}
                      padding="base"
                      border="base"
                      borderRadius="base"
                    >
                      <s-stack gap="base">
                        <s-stack direction="inline" gap="small" alignItems="start">
                          <s-stack gap="extra-small">
                            <s-text fontWeight="semibold">
                              {t(`feeds.markets.${code}.title`, { ccy })}
                            </s-text>
                            <s-text tone="subdued" size="small">
                              {t(`feeds.markets.${code}.subtitle`)}
                            </s-text>
                          </s-stack>
                          <s-badge tone={synced ? "success" : "warning"}>
                            {synced ? t("feeds.synced") : t("feeds.preparing")}
                          </s-badge>
                        </s-stack>
                        <s-stack direction="inline" gap="small" alignItems="center">
                          <s-text tone="subdued" size="small">
                            {t("feeds.listedCount")}
                          </s-text>
                          <s-text fontWeight="semibold">
                            {String(f.item_count ?? 0)}
                          </s-text>
                        </s-stack>
                        <s-stack direction="inline" gap="small" alignItems="center">
                          <s-text size="small">{f.url || ""}</s-text>
                          <s-button
                            variant="primary"
                            onClick={() => {
                              navigator.clipboard.writeText(f.url);
                              showMsg(t("feeds.copied"), "success");
                              setTimeout(() => showMsg("", "info"), 2000);
                            }}
                          >
                            {t("feeds.copyShort")}
                          </s-button>
                        </s-stack>
                      </s-stack>
                    </s-box>
                  );
                })}
              </s-grid>
            </s-stack>
          </s-box>
        </s-section>
      ) : null}

      {generating && (
        <s-section heading={t("pipeline.heading")}>
          <s-text>{steps[pipelineStep]?.copy || t("cta.generating")}</s-text>
        </s-section>
      )}

      {/* Card 1: store targeting + brand + sole generate CTA (above products) */}
      {!loading && (
        <s-section heading={t("hub.setupCard")}>
          <s-box padding="base" border="base" borderRadius="base">
            <s-stack gap="base">
              <s-stack gap="extra-small">
                <s-text fontWeight="semibold">{t("setup.platforms")}</s-text>
                <s-stack direction="inline" gap="small" style="flex-wrap: wrap">
                  {PLATFORMS.map((p) => (
                    <s-button
                      key={p.code}
                      variant={platforms.has(p.code) ? "primary" : "secondary"}
                      onClick={() => toggleInSet(platforms, p.code, setPlatforms)}
                    >
                      {p.label}
                    </s-button>
                  ))}
                </s-stack>
              </s-stack>

              <s-stack gap="base">
                <s-text fontWeight="semibold">{t("setup.markets")}</s-text>
                <s-stack direction="inline" gap="base" style="flex-wrap: wrap">
                  {LANGUAGES.map((c) => (
                    <s-button
                      key={c.code}
                      variant={languages.has(c.code) ? "primary" : "secondary"}
                      onClick={() => toggleMarket(c.code)}
                      disabled={!!marketChecking || generating}
                    >
                      {t(`setup.country.${c.code}`)}
                    </s-button>
                  ))}
                </s-stack>
                {marketHint ? (
                  <s-banner tone="warning">
                    <s-text>{marketHint}</s-text>
                  </s-banner>
                ) : null}
              </s-stack>

              <s-stack gap="small">
                {adBrandConfirmed && !brandEditOpen ? (
                  <s-stack direction="inline" gap="small" alignItems="center" style="flex-wrap: wrap">
                    <s-text tone="success" size="small">
                      {t("brand.confirmed", { brand: adBrand })}
                    </s-text>
                    <s-button variant="tertiary" onClick={() => setBrandEditOpen(true)}>
                      {t("brand.change")}
                    </s-button>
                  </s-stack>
                ) : (
                  <s-stack gap="small">
                    <s-text-field
                      label={t("brand.label")}
                      value={adBrand}
                      placeholder={t("brand.placeholder")}
                      onInput={(e) => setAdBrand(e.target?.value || "")}
                      disabled={adBrandSaving}
                    />
                    <s-button
                      variant="secondary"
                      disabled={adBrandSaving || !(adBrand || "").trim()}
                      onClick={saveAdBrand}
                    >
                      {adBrandSaving
                        ? t("brand.saving")
                        : adBrandConfirmed
                          ? t("brand.update")
                          : t("brand.confirm")}
                    </s-button>
                    {!adBrandConfirmed && (
                      <s-text tone="caution" size="small">
                        {t("overview.storeBrandGate")}
                      </s-text>
                    )}
                    {adBrandConfirmed && brandEditOpen && (
                      <s-button variant="tertiary" onClick={() => setBrandEditOpen(false)}>
                        {t("brand.cancelEdit")}
                      </s-button>
                    )}
                  </s-stack>
                )}
                {selected.size === 0 && (
                  <s-text tone="caution" size="small">
                    {t("hub.needProducts")}
                  </s-text>
                )}
                {billing && !affordable ? (
                  <s-stack gap="extra-small">
                    <s-text tone="caution" size="small">
                      {t("quota.insufficient")}
                    </s-text>
                    <s-button variant="secondary" onClick={() => setView("plans")}>
                      {t("billing.plans.open")}
                    </s-button>
                  </s-stack>
                ) : null}
                <s-button
                  variant="primary"
                  disabled={
                    generating ||
                    patching ||
                    imagePickerSaving ||
                    selected.size === 0 ||
                    !affordable ||
                    languages.size === 0 ||
                    platforms.size === 0 ||
                    !adBrandConfirmed
                  }
                  onClick={handleGenerate}
                >
                  {generating
                    ? t("cta.generating")
                    : feeds.length > 0
                      ? t("cta.updateWide")
                      : t("cta.create")}
                </s-button>
              </s-stack>
            </s-stack>
          </s-box>
        </s-section>
      )}

      {/* Card 2: product scope + list only */}
      {!loading && (
        <s-section heading={t("hub.productsCard")}>
          <s-box padding="base" border="base" borderRadius="base">
            <s-stack gap="base">
              <s-stack direction="inline" gap="small" style="flex-wrap: wrap">
                <s-button
                  variant={scopeType === "all" ? "primary" : "secondary"}
                  onClick={() => pickScope("all")}
                >
                  {t("scope.allActive", { n: activeProducts.length })}
                </s-button>
                {needsProductCount > 0 && (
                  <s-button
                    variant={scopeType === "needs" ? "primary" : "secondary"}
                    onClick={pickNeedsScope}
                  >
                    {t("scope.needsChip", { n: needsProductCount })}
                  </s-button>
                )}
                {typeChips.map(([key, n]) => {
                  const label =
                    key === "__uncategorized__"
                      ? t("scope.uncategorized", { n })
                      : t("scope.typeChip", { type: key, n });
                  return (
                    <s-button
                      key={key}
                      variant={scopeType === key ? "primary" : "secondary"}
                      onClick={() => pickScope(key)}
                    >
                      {label}
                    </s-button>
                  );
                })}
              </s-stack>

              <s-text fontWeight="semibold">
                {t("hub.productsInScope", {
                  selected: selected.size,
                  total: listedProducts.length,
                })}
              </s-text>
              {needsReview && (
                <s-text tone="subdued" size="small">
                  {t("products.needsInListHint", { n: needsProductCount })}
                </s-text>
              )}
              <s-stack direction="inline" gap="small" alignItems="center">
                <s-text-field
                  label={t("products.search")}
                  labelAccessibilityVisibility="exclusive"
                  placeholder={t("products.search")}
                  value={filter}
                  onInput={(e) => setFilter(e.target?.value || "")}
                />
                <s-button onClick={toggleAll} variant="secondary">
                  {listedProducts.length > 0 && listedProducts.every((p) => selected.has(p.id))
                    ? t("products.deselectAll")
                    : t("scope.selectScope")}
                </s-button>
              </s-stack>
              {renderBulkEditBar()}
              <s-stack gap="small">
                <s-box padding="small" border="base" borderRadius="base" background="subdued">
                  <s-stack gap="small">
                    {pagedProducts.map((p) => {
                      const hints = hintsFor(p);
                      return (
                      <s-box
                        key={p.id}
                        padding="small"
                        border="base"
                        borderRadius="base"
                        background="base"
                      >
                        <s-grid
                          gridTemplateColumns="auto auto 1fr"
                          gap="base"
                          alignItems="start"
                        >
                          <s-checkbox
                            checked={selected.has(p.id)}
                            onChange={() => toggleProduct(p.id)}
                            accessibilityLabel={t("products.selectA11y", { title: p.title })}
                          />
                          {p.image ? (
                            <s-thumbnail src={p.image} alt={p.title} size="large" />
                          ) : (
                            <s-thumbnail size="large" alt="" />
                          )}
                          <s-stack gap="extra-small">
                            <s-text fontWeight="semibold">{p.title}</s-text>
                            <s-text tone="subdued" size="small">
                              {t("products.variantCount", { n: p.variantCount })}
                              {p.productType ? ` · ${p.productType}` : ""}
                            </s-text>
                            <s-stack direction="inline" gap="small" style="flex-wrap: wrap">
                              {p.id ? (
                                <s-button variant="primary" href={shopifyAdminHref(p.id)}>
                                  {t("products.editInShopify")}
                                </s-button>
                              ) : null}
                              {hints.fixSkus.length > 0 && (
                                <s-button
                                  variant="secondary"
                                  onClick={() => fixThisProduct(p)}
                                  disabled={patching}
                                >
                                  {t("products.fixThis")}
                                </s-button>
                              )}
                              {hints.wordSkus.length > 0 && p.id ? (
                                <s-button variant="secondary" href={shopifyAdminHref(p.id)}>
                                  {t("products.fixWordingBtn")}
                                </s-button>
                              ) : null}
                            </s-stack>
                            {hints.fixSkus.map((sku) => {
                              const key = String(sku || "").toLowerCase();
                              return renderSkuFixLine(sku, {
                                needColor: hints.colorSkus.some(
                                  (s) => String(s).toLowerCase() === key,
                                ),
                                needSize: hints.sizeSkus.some(
                                  (s) => String(s).toLowerCase() === key,
                                ),
                              });
                            })}
                            {hints.imageSkus.map((sku) => {
                              const info = labelForSku(skuCatalog, sku);
                              const href = shopifyAdminHref(info.productId, info.variantId);
                              const label = info.variantTitle || sku;
                              return (
                                <s-stack
                                  key={`img-${sku}`}
                                  direction="inline"
                                  gap="small"
                                  alignItems="center"
                                >
                                  {href ? (
                                    <s-link href={href}>{label}</s-link>
                                  ) : (
                                    <s-text size="small">{label}</s-text>
                                  )}
                                  <s-button
                                    variant="secondary"
                                    onClick={() => openImagePicker(sku)}
                                    disabled={
                                      imagePickerLoading || imagePickerSaving || patching
                                    }
                                  >
                                    {t("quality.changeImage")}
                                  </s-button>
                                </s-stack>
                              );
                            })}
                          </s-stack>
                        </s-grid>
                      </s-box>
                      );
                    })}
                    {listedProducts.length === 0 && (
                      <s-text tone="subdued">{t("hub.emptyScope")}</s-text>
                    )}
                  </s-stack>
                </s-box>
                {listedProducts.length > PRODUCT_PAGE_SIZE && (
                  <s-stack
                    direction="inline"
                    gap="small"
                    alignItems="center"
                    style="flex-wrap: wrap"
                  >
                    <s-button
                      variant="secondary"
                      disabled={safeProductPage <= 0}
                      onClick={() => setProductListPage((p) => Math.max(0, p - 1))}
                    >
                      {t("hub.productListPrev")}
                    </s-button>
                    <s-text tone="subdued" size="small">
                      {t("hub.productListPage", {
                        from: safeProductPage * PRODUCT_PAGE_SIZE + 1,
                        to: Math.min(
                          listedProducts.length,
                          safeProductPage * PRODUCT_PAGE_SIZE + PRODUCT_PAGE_SIZE,
                        ),
                        n: listedProducts.length,
                      })}
                    </s-text>
                    <s-button
                      variant="secondary"
                      disabled={safeProductPage >= productPageCount - 1}
                      onClick={() =>
                        setProductListPage((p) => Math.min(productPageCount - 1, p + 1))
                      }
                    >
                      {t("hub.productListNext")}
                    </s-button>
                  </s-stack>
                )}
              </s-stack>
            </s-stack>
          </s-box>
        </s-section>
      )}

      {loading && (
        <s-section>
          <s-stack alignItems="center" padding="large-400">
            <s-spinner />
            <s-text tone="subdued">{t("products.loading")}</s-text>
          </s-stack>
        </s-section>
      )}

      {/* Store checklist — actionable open items with Shopify deep links */}
      {!generating && showStoreTodos && (
        <s-section heading={t("hub.checklistHeading")}>
          <s-box padding="base" border="base" borderRadius="base">
            <s-stack gap="base">
              <s-text tone="subdued" size="small">
                {t("hub.checklistHelp")}
              </s-text>

              {(() => {
                /** @type {{ key: string, title: string, href?: string, onFix?: () => void, fixLabel?: string }[]} */
                const openItems = [];

                if (!adBrandConfirmed) {
                  openItems.push({
                    key: "brand",
                    title: t("overview.storeBrandGate"),
                    onFix: () => setBrandEditOpen(true),
                    fixLabel: t("brand.confirm"),
                  });
                }

                if (storeGateCurrency) {
                  openItems.push({
                    key: "currency",
                    title: t("overview.storeCurrencyGate", {
                      count: blockedCountries.length,
                    }),
                    href: adminDeepLink("/settings/markets"),
                    fixLabel: t("compliance.fixMarkets"),
                  });
                }

                for (const c of storeCompliance?.checks || []) {
                  if (c.status === "pass") continue;
                  const loc = formatComplianceCheck(c);
                  const path = c.fix_admin_path || "";
                  openItems.push({
                    key: c.id || loc.message,
                    title: loc.message,
                    href: path ? adminDeepLink(path) : "",
                    fixLabel:
                      path.includes("menus")
                        ? t("compliance.fixMenus")
                        : path.includes("legal")
                          ? t("compliance.fixLegal")
                          : path.includes("markets")
                            ? t("compliance.fixMarkets")
                            : path.includes("pages")
                              ? t("compliance.fixPages")
                              : t("compliance.fixInShopify"),
                  });
                }

                return (
                  <s-stack gap="base">
                    {openItems.length > 0 && (
                      <s-stack gap="small">
                        <s-text fontWeight="semibold">
                          {t("compliance.openHeading", { n: openItems.length })}
                        </s-text>
                        {openItems.map((item) => (
                          <OpenCheckCard
                            key={item.key}
                            title={item.title}
                            href={item.href}
                            onFix={item.onFix}
                            fixLabel={item.fixLabel}
                          />
                        ))}
                      </s-stack>
                    )}

                    {!storeCompliance && (
                      <s-text tone="subdued" size="small">
                        {t("compliance.needRun")}
                      </s-text>
                    )}

                    {storeCompliance && openItems.length === 0 && (
                      <s-text tone="success" size="small">
                        {t("compliance.allPass")}
                      </s-text>
                    )}
                  </s-stack>
                );
              })()}

              <s-button
                variant="secondary"
                onClick={() => runStoreCompliance()}
                disabled={complianceLoading || languages.size === 0}
              >
                {complianceLoading ? t("compliance.running") : t("compliance.run")}
              </s-button>
            </s-stack>
          </s-box>
        </s-section>
      )}

      {imagePickerSku && (
        <s-section heading={t("images.heading")}>
          <s-stack gap="small">
            {imagePickerLoading && <s-text>{t("images.loading")}</s-text>}
            {!imagePickerLoading && (imagePickerData?.candidates || []).length > 0 && (
              <s-stack direction="inline" gap="small" style="flex-wrap: wrap">
                {(imagePickerData.candidates || []).map((c) => (
                  <s-box
                    key={c.url}
                    padding="extra-small"
                    border={c.url === imagePickerSelected ? "strong" : "base"}
                    borderRadius="base"
                    onClick={() => setImagePickerSelected(c.url)}
                  >
                    <s-image
                      src={c.url}
                      alt=""
                      aspectRatio="1/1"
                      objectFit="cover"
                      borderRadius="base"
                      inlineSize="96px"
                    />
                  </s-box>
                ))}
              </s-stack>
            )}
            <s-stack direction="inline" gap="small">
              <s-button
                variant="primary"
                onClick={saveImagePicker}
                disabled={imagePickerSaving || !imagePickerSelected || imagePickerLoading}
              >
                {imagePickerSaving ? t("images.saving") : t("images.save")}
              </s-button>
              <s-button variant="tertiary" onClick={closeImagePicker} disabled={imagePickerSaving}>
                {t("images.cancel")}
              </s-button>
            </s-stack>
          </s-stack>
        </s-section>
      )}

      {blockedCountries.length > 0 && (
        <s-section heading={t("currency.blockedHeading")}>
          {blockedCountries.map((b) => (
            <s-banner key={b.country} tone="warning">
              <s-text>
                {b.country}: {t("currency.fixHint")}
              </s-text>
            </s-banner>
          ))}
        </s-section>
      )}
    </s-page>
  );
}
