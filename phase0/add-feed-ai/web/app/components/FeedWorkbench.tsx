import { useMemo, useState, useEffect, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { t } from "../lib/i18n";
import {
  type ComplianceCheck,
  type FeedInfo,
  type WorkbenchProduct,
  patchShopifyVariantAttrs,
  feedDownloadCsvUrl,
  patchFeedRows,
  fetchFeedPreview,
} from "../lib/adfeed-api";
import { ProductFeedDrawer } from "./ProductFeedDrawer";
import { localizeComplianceCheck } from "../lib/compliance-label";
import styles from "./FeedWorkbench.module.css";

type Props = {
  products: WorkbenchProduct[];
  selected: Set<string>;
  setSelected: (next: Set<string>) => void;
  platform: string;
  country: string;
  platforms: string[];
  feed: FeedInfo | null;
  feedExists: boolean;
  compliance: {
    light: string;
    summary?: { pass?: number; warn?: number; fail?: number };
    checks?: ComplianceCheck[];
  } | null;
  complianceLoading?: boolean;
  search: string;
  setSearch: (v: string) => void;
  withToken: <T>(fn: (token: string) => Promise<T>) => Promise<T>;
  copyUrl: (url: string) => void;
  onSavedEdits: () => void;
  onMessage: (
    text: string,
    tone?: "info" | "success" | "warning" | "critical",
  ) => void;
  /** Channels / markets / brand / generate — right sidebar above compliance. */
  setupSlot?: ReactNode;
  busy?: boolean;
  /** Merge-generate one product into the current durable XML. */
  onGenerateOne?: (productId: string) => void;
};

function feedStatusTag(p: WorkbenchProduct): {
  kind: "generated" | "pending" | "error";
  label: string;
} {
  const status = p.feed_status || "pending";
  if (status === "pending") {
    return { kind: "pending", label: t("workbench.tagPending") };
  }
  if (status === "missing") {
    return { kind: "error", label: t("workbench.tagFailed") };
  }
  return {
    kind: "generated",
    label: t("workbench.tagInFeed", { n: p.feed_item_count ?? 0 }),
  };
}

function defectParts(p: WorkbenchProduct): string[] {
  const out: string[] = [];
  if (p.need_color) out.push(t("workbench.hintMissingColor"));
  if (p.need_size) out.push(t("workbench.hintMissingSize"));
  if (p.need_image) out.push(t("workbench.hintMissingImage"));
  return out;
}

function hasMandatoryGaps(_p: WorkbenchProduct): boolean {
  // Soft suggestions only — never hard-block generate on color/size/image.
  return false;
}

/** Pending + required gaps: cannot batch-generate; checkbox off. */
function blockGenerateSelect(p: WorkbenchProduct): boolean {
  const pending = (p.feed_status || "pending") === "pending";
  return pending && hasMandatoryGaps(p);
}

/** Red Fix-then-generate — unused for attr gaps; main action stays Generate. */
function needsFixBeforeGenerate(_p: WorkbenchProduct): boolean {
  return false;
}

function hasOptionalFix(p: WorkbenchProduct): boolean {
  return Boolean(p.need_color || p.need_size || p.need_image);
}

function displayProductType(key: string): string {
  if (key === "我的商店") return t("scope.myStoreType");
  return key;
}

function sortChecks(checks: ComplianceCheck[]): ComplianceCheck[] {
  const rank = (s: string) =>
    s === "warn" ? 0 : s === "unknown" ? 1 : 2;
  return [...checks].sort((a, b) => rank(a.status) - rank(b.status));
}

function visibleComplianceChecks(checks: ComplianceCheck[]): ComplianceCheck[] {
  return sortChecks(checks).filter((c) => c.status !== "pass");
}

export function FeedWorkbench(props: Props) {
  const {
    products,
    selected,
    setSelected,
    platform,
    country,
    platforms,
    feed,
    feedExists,
    compliance,
    complianceLoading,
    search,
    setSearch,
    withToken,
    copyUrl,
    onSavedEdits,
    onMessage,
    setupSlot,
    busy,
    onGenerateOne,
  } = props;

  const navigate = useNavigate();
  const [editing, setEditing] = useState<WorkbenchProduct | null>(null);
  const [editFocus, setEditFocus] = useState<"color" | "size" | null>(null);
  const [quickFix, setQuickFix] = useState<{
    product: WorkbenchProduct;
    field: "color" | "size";
  } | null>(null);
  const [quickValue, setQuickValue] = useState("");
  const [quickSaving, setQuickSaving] = useState(false);
  const [quickFixError, setQuickFixError] = useState("");
  /** all | needs | product_type key | __uncategorized__ */
  const [scopeType, setScopeType] = useState<string>("all");

  const typeKey = (p: WorkbenchProduct) => {
    const raw = String(p.product_type || "").trim();
    return raw || "__uncategorized__";
  };

  const needsCount = useMemo(
    () =>
      products.filter(
        (p) => p.needs_attention || p.need_color || p.need_size || p.need_image,
      ).length,
    [products],
  );

  const typeChips = useMemo(() => {
    const m = new Map<string, number>();
    for (const p of products) {
      const k = typeKey(p);
      m.set(k, (m.get(k) || 0) + 1);
    }
    return Array.from(m.entries()).sort((a, b) => {
      if (a[0] === "__uncategorized__") return -1;
      if (b[0] === "__uncategorized__") return 1;
      return a[0].localeCompare(b[0]);
    });
  }, [products]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let list = products;
    if (scopeType === "needs") {
      list = list.filter(
        (p) => p.needs_attention || p.need_color || p.need_size || p.need_image,
      );
    } else if (scopeType !== "all") {
      list = list.filter((p) => typeKey(p) === scopeType);
    }
    if (q) {
      list = list.filter(
        (p) =>
          (p.title || "").toLowerCase().includes(q) ||
          String(p.id).toLowerCase().includes(q) ||
          String(p.product_type || "")
            .toLowerCase()
            .includes(q),
      );
    }
    return [...list].sort((a, b) => {
      const ha =
        a.needs_attention || a.need_color || a.need_size || a.need_image
          ? 0
          : 1;
      const hb =
        b.needs_attention || b.need_color || b.need_size || b.need_image
          ? 0
          : 1;
      return ha - hb;
    });
  }, [products, search, scopeType]);

  const selectScoped = () => {
    const ids = filtered
      .filter((p) => !blockGenerateSelect(p))
      .map((p) => p.id);
    const allOn = ids.length > 0 && ids.every((id) => selected.has(id));
    if (allOn) {
      const next = new Set(selected);
      for (const id of ids) next.delete(id);
      setSelected(next);
    } else {
      setSelected(new Set([...selected, ...ids]));
    }
  };

  useEffect(() => {
    const blocked = new Set(
      products.filter(blockGenerateSelect).map((p) => p.id),
    );
    if (!blocked.size) return;
    const next = new Set(selected);
    let changed = false;
    for (const id of blocked) {
      if (next.delete(id)) changed = true;
    }
    if (changed) setSelected(next);
    // Prune blocked rows when workbench data refreshes only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [products]);

  const openAttrFix = (
    p: WorkbenchProduct,
    field: "color" | "size",
  ) => {
    const pending = (p.feed_status || "pending") === "pending";
    const inFeed = !pending && (p.feed_item_count || 0) > 0;
    if (inFeed) {
      setEditFocus(field);
      setEditing(p);
      return;
    }
    setQuickValue("");
    setQuickFixError("");
    setQuickFix({ product: p, field });
  };

  const openRowFix = (p: WorkbenchProduct) => {
    if (p.need_color) {
      openAttrFix(p, "color");
      return;
    }
    if (p.need_size) {
      openAttrFix(p, "size");
      return;
    }
    if (p.need_image) {
      setEditFocus(null);
      setEditing(p);
      return;
    }
    setEditing(p);
  };

  const saveQuickFix = async () => {
    if (!quickFix) return;
    const value = quickValue.trim();
    if (!value) {
      onMessage(t("workbench.fixNeedValue"), "warning");
      return;
    }
    const p = quickFix.product;
    const field = quickFix.field;
    setQuickSaving(true);
    setQuickFixError("");
    try {
      let skus = [...(p.variant_skus || [])].filter(Boolean);
      if (!skus.length && (p.feed_item_count || 0) > 0) {
        const prev = await withToken((token) =>
          fetchFeedPreview(token, platform, country, {
            productId: p.id,
            limit: 100,
            offset: 0,
          }),
        );
        skus = (prev.items || []).map((i) => i.sku).filter(Boolean);
      }
      // Demo / supplier products often have empty SKUs — still patch all variants.
      const inFeed = (p.feed_item_count || 0) > 0;
      console.info("[quickFix] save", {
        productId: p.id,
        title: p.title,
        field,
        value,
        skus,
        inFeed,
      });
      if (inFeed) {
        if (!skus.length) {
          const msg = t("workbench.fixNoSkus");
          setQuickFixError(msg);
          onMessage(msg, "warning");
          return;
        }
        await withToken((token) =>
          patchFeedRows(
            token,
            skus.map((sku) =>
              field === "color" ? { sku, color: value } : { sku, size: value },
            ),
            platforms,
            [country],
            true,
          ),
        );
        onMessage(t("workbench.fixSavedInFeed"), "success");
      } else {
        const patches = skus.length
          ? skus.map((sku) =>
              field === "color" ? { sku, color: value } : { sku, size: value },
            )
          : [
              field === "color"
                ? { sku: "", color: value }
                : { sku: "", size: value },
            ];
        const result = await withToken((token) =>
          patchShopifyVariantAttrs(token, p.id, patches),
        );
        console.info("[quickFix] shopify result", result);
        const skipped = Boolean(result.skipped_no_option);
        const updatedN = result.updated?.length || 0;
        if (!updatedN && !result.partial && !skipped) {
          throw new Error(result.message || t("workbench.fixNoSkus"));
        }
        const msg =
          result.message || t("workbench.fixSavedShopify");
        onMessage(msg, result.partial ? "warning" : "success");
        const stillNeedsSize =
          !skipped &&
          field === "color" &&
          Boolean(result.need_size);
        setQuickFix(null);
        setQuickValue("");
        setQuickFixError("");
        onSavedEdits();
        if (stillNeedsSize) {
          setTimeout(() => {
            openAttrFix(
              { ...p, need_color: false, need_size: true },
              "size",
            );
          }, 0);
        }
        return;
      }
      setQuickFix(null);
      setQuickValue("");
      setQuickFixError("");
      onSavedEdits();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setQuickFixError(msg);
      onMessage(msg, "critical");
    } finally {
      setQuickSaving(false);
    }
  };

  const toggle = (id: string) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  const downloadCsv = async () => {
    if (!feedExists) {
      onMessage(t("workbench.needGenerate"), "warning");
      return;
    }
    try {
      const token = await withToken(async (tkn) => tkn);
      const url = feedDownloadCsvUrl(platform, country);
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`CSV ${res.status}`);
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${platform}_${country.toLowerCase()}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
      onMessage(t("feeds.csvDownloaded"), "success");
    } catch (e) {
      onMessage(e instanceof Error ? e.message : String(e), "critical");
    }
  };

  const openFeedEditor = () => {
    if (!feed?.url) {
      onMessage(t("workbench.needGenerate"), "warning");
      return;
    }
    navigate(
      `/app/feed?platform=${encodeURIComponent(platform)}&country=${encodeURIComponent(country)}`,
    );
  };

  return (
    <div
      className={styles.shell}
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 1fr) 280px",
        gap: 16,
        alignItems: "start",
        width: "100%",
      }}
    >
      <div className={styles.main}>
        <s-stack gap="base">
          <s-stack gap="small">
            <s-stack direction="inline" gap="small">
              <s-button
                variant={scopeType === "all" ? "primary" : "secondary"}
                onClick={() => setScopeType("all")}
              >
                {t("scope.allActive", { n: products.length })}
              </s-button>
              {needsCount > 0 ? (
                <s-button
                  variant={scopeType === "needs" ? "primary" : "secondary"}
                  onClick={() => setScopeType("needs")}
                >
                  {t("scope.needsChip", { n: needsCount })}
                </s-button>
              ) : null}
              {typeChips.map(([key, n]) => (
                <s-button
                  key={key}
                  variant={scopeType === key ? "primary" : "secondary"}
                  onClick={() => setScopeType(key)}
                >
                  {key === "__uncategorized__"
                    ? t("scope.uncategorized", { n })
                    : t("scope.typeChip", {
                        type: displayProductType(key),
                        n,
                      })}
                </s-button>
              ))}
            </s-stack>
            <s-stack direction="inline" gap="small" alignItems="center">
              <s-text tone="neutral">
                {t("scope.inScope", {
                  selected: selected.size,
                  total: filtered.length,
                })}
              </s-text>
              <s-button variant="secondary" onClick={selectScoped}>
                {t("scope.selectScope")}
              </s-button>
            </s-stack>
          </s-stack>

          <s-text-field
            label={t("workbench.search")}
            value={search}
            onInput={(e: Event) =>
              setSearch((e.target as HTMLInputElement).value || "")
            }
          />

          <div className={styles.tablePane}>
            <s-stack gap="small">
              {filtered.map((p) => {
                const checked = selected.has(p.id);
                const pending = (p.feed_status || "pending") === "pending";
                const fixFirst = needsFixBeforeGenerate(p);
                const selectBlocked = blockGenerateSelect(p);
                const optionalFix = hasOptionalFix(p);
                const tag = feedStatusTag(p);
                const defects = defectParts(p);
                const actionLabel = fixFirst
                  ? t("workbench.fixThenGenerate")
                  : tag.label;
                const actionClass = fixFirst
                  ? styles.statusActionFix
                  : pending
                    ? styles.statusActionPending
                    : styles.statusActionInFeed;
                const onStatusAction = () => {
                  if (fixFirst) {
                    openRowFix(p);
                    return;
                  }
                  if (pending) {
                    onGenerateOne?.(p.id);
                    return;
                  }
                  setEditing(p);
                };
                return (
                  <div key={p.id} className={styles.productCard}>
                    <div
                      className={`${styles.checkboxWrap}${
                        selectBlocked ? ` ${styles.checkboxDisabled}` : ""
                      }`}
                    >
                      <s-checkbox
                        checked={checked}
                        disabled={selectBlocked}
                        onChange={() => {
                          if (!selectBlocked) toggle(p.id);
                        }}
                      />
                    </div>
                    {p.image_url ? (
                      <img
                        className={styles.thumb}
                        src={p.image_url}
                        alt=""
                      />
                    ) : (
                      <div className={styles.thumbEmpty}>—</div>
                    )}
                    <div className={styles.cardContent}>
                      <div className={styles.cardHeaderRow}>
                        <div className={styles.cardMain}>
                          <h4 className={styles.productTitle}>
                            {p.title || p.id}
                          </h4>
                          {defects.length ? (
                            <div className={styles.statusRow}>
                              <button
                                type="button"
                                className={styles.defectFixBtn}
                                onClick={() => openRowFix(p)}
                              >
                                {t("workbench.defectsLine", {
                                  list: defects.join("、"),
                                })}
                                {optionalFix
                                  ? ` · ${t("workbench.fixOptional")}`
                                  : ""}
                              </button>
                            </div>
                          ) : null}
                        </div>
                        <button
                          type="button"
                          className={`${styles.statusAction} ${actionClass}`}
                          disabled={
                            !fixFirst &&
                            pending &&
                            (Boolean(busy) || !onGenerateOne)
                          }
                          onClick={onStatusAction}
                        >
                          {actionLabel}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
              {!filtered.length ? (
                <s-text tone="neutral">{t("workbench.emptyProducts")}</s-text>
              ) : null}
            </s-stack>
          </div>

          {quickFix ? (
            <>
              <button
                type="button"
                className={styles.drawerBackdrop}
                aria-label={t("workbench.close")}
                onClick={() => setQuickFix(null)}
              />
              <div className={styles.quickFixCard} role="dialog" aria-modal="true">
                <s-box padding="base" border="base" borderRadius="base">
                  <s-stack gap="base">
                    <s-text type="strong">
                      {quickFix.field === "color"
                        ? t("workbench.fixColorTitle", {
                            title: quickFix.product.title || quickFix.product.id,
                          })
                        : t("workbench.fixSizeTitle", {
                            title: quickFix.product.title || quickFix.product.id,
                          })}
                    </s-text>
                    <s-text>
                      {quickFix.field === "color"
                        ? t("workbench.fixColorHelp")
                        : t("workbench.fixSizeHelp")}
                    </s-text>
                    <s-text-field
                      label={
                        quickFix.field === "color"
                          ? t("feeds.colAdColor")
                          : t("feeds.colAdSize")
                      }
                      value={quickValue}
                      placeholder={
                        quickFix.field === "color"
                          ? t("quality.colorPh")
                          : t("quality.sizePh")
                      }
                      onInput={(e: Event) =>
                        setQuickValue(
                          (e.target as HTMLInputElement).value || "",
                        )
                      }
                      disabled={quickSaving}
                    />
                    {quickFixError ? (
                      <p className={styles.quickFixError} role="alert">
                        {quickFixError}
                      </p>
                    ) : null}
                    <s-stack direction="inline" gap="small">
                      <s-button
                        variant="secondary"
                        disabled={quickSaving}
                        onClick={() => setQuickFix(null)}
                      >
                        {t("workbench.cancel")}
                      </s-button>
                      <s-button
                        variant="primary"
                        disabled={quickSaving || !quickValue.trim()}
                        onClick={() => void saveQuickFix()}
                      >
                        {quickSaving
                          ? t("quality.applying")
                          : t("workbench.fixSave")}
                      </s-button>
                    </s-stack>
                  </s-stack>
                </s-box>
              </div>
            </>
          ) : null}

          {editing ? (
            <>
              <button
                type="button"
                className={styles.drawerBackdrop}
                aria-label={t("workbench.close")}
                onClick={() => {
                  setEditing(null);
                  setEditFocus(null);
                }}
              />
              <div className={styles.drawerPanel} role="dialog" aria-modal="true">
                <ProductFeedDrawer
                  product={editing}
                  platform={platform}
                  country={country}
                  platforms={platforms}
                  withToken={withToken}
                  focusField={editFocus}
                  onClose={() => {
                    setEditing(null);
                    setEditFocus(null);
                  }}
                  onSaved={onSavedEdits}
                  onMessage={onMessage}
                />
              </div>
            </>
          ) : null}
        </s-stack>
      </div>

      <aside className={styles.sidebar}>
        {setupSlot ? (
          <div className={`${styles.sideCard} ${styles.sideCardLive}`}>
            <div className={styles.setupCardBody}>{setupSlot}</div>
          </div>
        ) : null}

        <div className={`${styles.sideCard} ${styles.sideCardLive}`}>
          {feed?.url ? (
            <div className={styles.feedCard}>
              <a
                className={styles.feedUrlBox}
                href={feed.url}
                target="_blank"
                rel="noopener noreferrer"
                title={feed.url}
              >
                <span className={styles.feedUrlLabel}>{t("feeds.urlLabel")}</span>
                <span className={styles.feedUrlText}>{feed.url}</span>
              </a>
              <div className={styles.feedActions}>
                <button
                  type="button"
                  className={styles.feedActionPrimary}
                  onClick={() => openFeedEditor()}
                >
                  {t("feeds.editAllFeed")}
                </button>
                <div className={styles.feedActionRow}>
                  <button
                    type="button"
                    className={styles.feedActionSecondary}
                    onClick={() => void copyUrl(feed.url)}
                  >
                    {t("feeds.copy")}
                  </button>
                  <button
                    type="button"
                    className={styles.feedActionSecondary}
                    onClick={() => void downloadCsv()}
                  >
                    {t("feeds.downloadCsv")}
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <s-text tone="neutral">{t("workbench.needGenerate")}</s-text>
          )}
        </div>

        <div className={styles.sideCard}>
          <div className={styles.auditHead}>
            <div className={styles.auditTitle}>{t("workbench.compliance")}</div>
          </div>

          {complianceLoading ? (
            <p className={styles.auditMuted}>{t("compliance.running")}</p>
          ) : compliance ? (
            (() => {
              const warnN = compliance.summary?.warn ?? 0;
              const unknownN = compliance.summary?.unknown ?? 0;
              const items = visibleComplianceChecks(compliance.checks || []);
              const summaryText =
                warnN > 0
                  ? t("workbench.complianceSummary", { warn: warnN })
                  : unknownN > 0
                    ? t("workbench.complianceSummaryUnknown", { unknown: unknownN })
                    : t("workbench.complianceSummaryClear");
              return (
            <>
              <div className={styles.auditSummary}>
                <span
                  className={`${styles.auditDot} ${
                    warnN > 0 ? styles.auditDotWarn : styles.auditDotOk
                  }`}
                />
                <span className={styles.auditSummaryText}>{summaryText}</span>
              </div>
              {items.length ? (
              <ul className={styles.auditList}>
                {items.slice(0, 8).map((c) => {
                    const href = c.fix_admin_path
                      ? `shopify:admin/${c.fix_admin_path.replace(/^\//, "")}`
                      : "";
                    return (
                      <li key={c.id} className={styles.auditItem}>
                        <span className={styles.auditIconWarn} />
                        <div className={styles.auditLabel}>
                          {localizeComplianceCheck(c)}
                          {href ? (
                            <>
                              <br />
                              <a href={href}>{t("compliance.fixInShopify")}</a>
                            </>
                          ) : null}
                        </div>
                      </li>
                    );
                  })}
              </ul>
              ) : (
                <p className={styles.auditMuted}>{summaryText}</p>
              )}
            </>
              );
            })()
          ) : (
            <p className={styles.auditMuted}>{t("workbench.complianceEmpty")}</p>
          )}
        </div>
      </aside>
    </div>
  );
}
