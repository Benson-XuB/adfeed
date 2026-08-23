import { useEffect, useState } from "react";
import { t } from "../lib/i18n";
import {
  type FeedPreviewItem,
  type WorkbenchProduct,
  deleteFeedRows,
  fetchFeedImageCandidates,
  fetchFeedPreview,
  patchFeedRows,
} from "../lib/adfeed-api";
import styles from "./ProductFeedDrawer.module.css";

type Props = {
  product: WorkbenchProduct;
  platform: string;
  country: string;
  platforms: string[];
  withToken: <T>(fn: (token: string) => Promise<T>) => Promise<T>;
  onClose: () => void;
  onSaved: () => void;
  onMessage: (text: string, tone?: "info" | "success" | "warning" | "critical") => void;
  /** When opened from 缺颜色 / 缺尺码 badge */
  focusField?: "color" | "size" | null;
};

export function ProductFeedDrawer({
  product,
  platform,
  country,
  platforms,
  withToken,
  onClose,
  onSaved,
  onMessage,
  focusField = null,
}: Props) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deletingSku, setDeletingSku] = useState<string | null>(null);
  const [items, setItems] = useState<FeedPreviewItem[]>([]);
  const [drafts, setDrafts] = useState<Record<string, FeedPreviewItem>>({});
  const [imageSku, setImageSku] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<Array<{ url: string }>>([]);
  const [bulkValue, setBulkValue] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void withToken((token) =>
      fetchFeedPreview(token, platform, country, {
        productId: product.id,
        limit: 100,
        offset: 0,
      }),
    )
      .then((data) => {
        if (cancelled) return;
        setItems(data.items || []);
        setDrafts({});
      })
      .catch((e) => {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : String(e);
        if (/404|not found|generate first/i.test(msg)) {
          setItems([]);
        } else {
          onMessage(msg, "critical");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [product.id, platform, country, withToken, onMessage]);

  const draftOf = (row: FeedPreviewItem) => drafts[row.sku] || row;
  const hasEdits = Object.keys(drafts).length > 0;

  const setField = (
    sku: string,
    field: "title" | "color" | "size" | "image_url",
    value: string,
  ) => {
    setDrafts((prev) => {
      const base = prev[sku] || items.find((i) => i.sku === sku);
      if (!base) return prev;
      return { ...prev, [sku]: { ...base, [field]: value } };
    });
  };

  const applyBulkToAll = () => {
    const v = bulkValue.trim();
    if (!v || !focusField) return;
    setDrafts((prev) => {
      const next = { ...prev };
      for (const row of items) {
        const base = next[row.sku] || row;
        next[row.sku] = { ...base, [focusField]: v };
      }
      return next;
    });
    onMessage(
      focusField === "color"
        ? t("workbench.bulkColorApplied", { value: v })
        : t("workbench.bulkSizeApplied", { value: v }),
      "success",
    );
  };

  const save = async () => {
    const patches = Object.values(drafts)
      .map((d) => {
        const orig = items.find((i) => i.sku === d.sku);
        if (!orig) return null;
        const patch: {
          sku: string;
          title?: string;
          color?: string;
          size?: string;
          image_url?: string;
        } = { sku: d.sku };
        if (d.title !== orig.title) patch.title = d.title;
        if (d.color !== orig.color) patch.color = d.color;
        if (d.size !== orig.size) patch.size = d.size;
        if (d.image_url && d.image_url !== orig.image_url) {
          patch.image_url = d.image_url;
        }
        if (
          patch.title == null &&
          patch.color == null &&
          patch.size == null &&
          patch.image_url == null
        ) {
          return null;
        }
        return patch;
      })
      .filter(Boolean) as Array<{
      sku: string;
      title?: string;
      color?: string;
      size?: string;
      image_url?: string;
    }>;

    if (!patches.length) {
      onMessage(t("feeds.noEdits"), "warning");
      return;
    }
    setSaving(true);
    try {
      const result = await withToken((token) =>
        patchFeedRows(token, patches, platforms, [country], true),
      );
      onMessage(result.message || t("feeds.applyOk"), "success");
      onSaved();
      onClose();
    } catch (e) {
      onMessage(e instanceof Error ? e.message : String(e), "critical");
    } finally {
      setSaving(false);
    }
  };

  const loadImages = async (sku: string) => {
    setImageSku(sku);
    try {
      const ctx = await withToken((token) =>
        fetchFeedImageCandidates(token, sku),
      );
      setCandidates(ctx.candidates || []);
    } catch (e) {
      onMessage(e instanceof Error ? e.message : String(e), "critical");
    }
  };

  const deleteOneRow = async (sku: string) => {
    if (!window.confirm(t("feeds.deleteRowConfirm"))) return;
    setDeletingSku(sku);
    try {
      const result = await withToken((token) =>
        deleteFeedRows(token, [sku], platforms, [country]),
      );
      setItems((prev) => prev.filter((i) => i.sku !== sku));
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[sku];
        return next;
      });
      if (imageSku === sku) {
        setImageSku(null);
        setCandidates([]);
      }
      onMessage(result.message || t("feeds.rowDeleted"), "success");
      onSaved();
    } catch (e) {
      onMessage(e instanceof Error ? e.message : String(e), "critical");
    } finally {
      setDeletingSku(null);
    }
  };

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.headerRow}>
          <h2 className={styles.headerTitle}>
            {t("workbench.drawerTitle", { title: product.title || product.id })}
          </h2>
          <s-button variant="tertiary" onClick={onClose}>
            {t("workbench.close")}
          </s-button>
        </div>
        <div className={styles.headerHintBlock}>
          <s-banner tone="info">
            <s-text>{t("workbench.drawerHint")}</s-text>
          </s-banner>
          <button
            type="button"
            className={styles.headerSaveBtn}
            disabled={saving || !hasEdits}
            onClick={() => void save()}
          >
            {saving ? t("feeds.applying") : t("workbench.saveApply")}
          </button>
        </div>
      </header>

      <div className={styles.body}>
        {focusField && items.length ? (
          <s-banner tone="warning">
            <s-stack gap="small">
              <s-text>
                {focusField === "color"
                  ? t("workbench.fixColorPrompt")
                  : t("workbench.fixSizePrompt")}
              </s-text>
              <s-stack direction="inline" gap="small" alignItems="end">
                <s-text-field
                  label={
                    focusField === "color"
                      ? t("feeds.colAdColor")
                      : t("feeds.colAdSize")
                  }
                  value={bulkValue}
                  placeholder={
                    focusField === "color"
                      ? t("quality.colorPh")
                      : t("quality.sizePh")
                  }
                  onInput={(e: Event) =>
                    setBulkValue((e.target as HTMLInputElement).value || "")
                  }
                />
                <s-button
                  variant="primary"
                  disabled={!bulkValue.trim()}
                  onClick={applyBulkToAll}
                >
                  {t("workbench.applyToAllSkus")}
                </s-button>
              </s-stack>
            </s-stack>
          </s-banner>
        ) : null}

        {loading ? (
          <s-text>{t("feeds.loading")}</s-text>
        ) : !items.length ? (
          <s-text tone="neutral">{t("workbench.noFeedItems")}</s-text>
        ) : (
          items.map((row) => {
            const d = draftOf(row);
            return (
              <div key={row.sku} className={styles.skuCard}>
                <s-stack gap="small">
                  <s-stack direction="inline" gap="base">
                    {d.image_url ? (
                      <img
                        src={d.image_url}
                        alt=""
                        width={48}
                        height={48}
                        style={{ objectFit: "cover", borderRadius: 6 }}
                      />
                    ) : null}
                    <s-stack gap="small">
                      <s-text type="strong">{row.sku}</s-text>
                      {row.issue ? (
                        <s-badge tone="warning">{row.issue}</s-badge>
                      ) : null}
                    </s-stack>
                  </s-stack>
                  <s-text-field
                    label={t("feeds.colAdTitle")}
                    value={d.title}
                    onInput={(e: Event) =>
                      setField(
                        row.sku,
                        "title",
                        (e.target as HTMLInputElement).value,
                      )
                    }
                  />
                  <s-stack direction="inline" gap="small">
                    <s-text-field
                      label={t("feeds.colAdColor")}
                      value={d.color}
                      onInput={(e: Event) =>
                        setField(
                          row.sku,
                          "color",
                          (e.target as HTMLInputElement).value,
                        )
                      }
                    />
                    <s-text-field
                      label={t("feeds.colAdSize")}
                      value={d.size}
                      onInput={(e: Event) =>
                        setField(
                          row.sku,
                          "size",
                          (e.target as HTMLInputElement).value,
                        )
                      }
                    />
                  </s-stack>
                  <s-text tone="neutral">{d.price}</s-text>
                  <div className={styles.skuActionRow}>
                    <button
                      type="button"
                      className={styles.skuActionBtn}
                      disabled={Boolean(deletingSku)}
                      onClick={() => void loadImages(row.sku)}
                    >
                      {t("feeds.pickImage")}
                    </button>
                    <button
                      type="button"
                      className={`${styles.skuActionBtn} ${styles.skuActionDelete}`}
                      disabled={deletingSku === row.sku}
                      onClick={() => void deleteOneRow(row.sku)}
                    >
                      {deletingSku === row.sku
                        ? t("feeds.deletingRow")
                        : t("workbench.deleteFeedRow")}
                    </button>
                  </div>
                  {imageSku === row.sku && candidates.length ? (
                    <s-stack direction="inline" gap="small">
                      {candidates.slice(0, 8).map((c) => (
                        <s-button
                          key={c.url}
                          variant="secondary"
                          onClick={() => {
                            setField(row.sku, "image_url", c.url);
                            setImageSku(null);
                          }}
                        >
                          <img
                            src={c.url}
                            alt=""
                            width={40}
                            height={40}
                            style={{ objectFit: "cover" }}
                          />
                        </s-button>
                      ))}
                    </s-stack>
                  ) : null}
                </s-stack>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
