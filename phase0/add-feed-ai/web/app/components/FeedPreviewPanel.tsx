import { useCallback, useEffect, useState } from "react";
import { t } from "../lib/i18n";
import {
  type FeedInfo,
  type FeedPreviewItem,
  type FeedSnapshot,
  feedDownloadCsvUrl,
  fetchFeedImageCandidates,
  fetchFeedPreview,
  fetchFeedSnapshots,
  getBackendUrl,
  deleteFeedRows,
  patchFeedRows,
  restoreFeedSnapshot,
} from "../lib/adfeed-api";

type Props = {
  feed: FeedInfo;
  withToken: <T>(fn: (token: string) => Promise<T>) => Promise<T>;
  platforms: string[];
  onApplied: (feeds?: FeedInfo[]) => void;
  onMessage: (text: string, tone?: "info" | "success" | "warning" | "critical") => void;
  copyUrl: (url: string) => void;
  /** inline = sidebar toggle; page = full /app/feed route */
  mode?: "inline" | "page";
};

export function FeedPreviewPanel({
  feed,
  withToken,
  platforms,
  onApplied,
  onMessage,
  copyUrl,
  mode = "inline",
}: Props) {
  const platform = (feed.platform || "google").toLowerCase();
  const country = String(feed.country || "US").toUpperCase();
  const isPage = mode === "page";

  const [open, setOpen] = useState(isPage);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState<FeedPreviewItem[]>([]);
  const [drafts, setDrafts] = useState<Record<string, FeedPreviewItem>>({});
  const [snapshots, setSnapshots] = useState<FeedSnapshot[]>([]);
  const [imageSku, setImageSku] = useState<string | null>(null);
  const [imageCandidates, setImageCandidates] = useState<
    Array<{ url: string; risky?: boolean }>
  >([]);
  const [saving, setSaving] = useState(false);
  const [savingSku, setSavingSku] = useState<string | null>(null);
  const [deletingSku, setDeletingSku] = useState<string | null>(null);
  const limit = 10;

  const load = useCallback(
    async (nextOffset = 0, query = q) => {
      setLoading(true);
      try {
        const data = await withToken((token) =>
          fetchFeedPreview(token, platform, country, {
            limit,
            offset: nextOffset,
            q: query,
          }),
        );
        setItems(data.items || []);
        setTotal(data.total || 0);
        setOffset(nextOffset);
        setDrafts({});
        const snaps = await withToken((token) =>
          fetchFeedSnapshots(token, platform, country),
        );
        setSnapshots(snaps.snapshots || []);
      } catch (e) {
        onMessage(e instanceof Error ? e.message : String(e), "critical");
      } finally {
        setLoading(false);
      }
    },
    [withToken, platform, country, q, onMessage],
  );

  useEffect(() => {
    if (open || isPage) void load(0, q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, isPage]);

  const draftOf = (row: FeedPreviewItem) => drafts[row.sku] || row;

  const setDraftField = (
    sku: string,
    field: "title" | "color" | "size",
    value: string,
  ) => {
    setDrafts((prev) => {
      const base = prev[sku] || items.find((i) => i.sku === sku);
      if (!base) return prev;
      return { ...prev, [sku]: { ...base, [field]: value } };
    });
  };

  const downloadCsv = async () => {
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

  const openXml = () => {
    const base = getBackendUrl().replace(/\/$/, "");
    const marker = "/feeds/";
    const idx = (feed.url || "").indexOf(marker);
    if (base && idx >= 0) {
      window.open(`${base}${feed.url.slice(idx)}`, "_blank", "noopener,noreferrer");
      return;
    }
    if (feed.url) window.open(feed.url, "_blank", "noopener,noreferrer");
  };

  type RowPatch = {
    sku: string;
    title?: string;
    color?: string;
    size?: string;
    image_url?: string;
  };

  const buildRowPatch = (
    draft: FeedPreviewItem,
    orig: FeedPreviewItem,
  ): RowPatch | null => {
    const patch: RowPatch = { sku: draft.sku };
    if (draft.title !== orig.title) patch.title = draft.title;
    if (draft.color !== orig.color) patch.color = draft.color;
    if (draft.size !== orig.size) patch.size = draft.size;
    if (draft.image_url && draft.image_url !== orig.image_url) {
      patch.image_url = draft.image_url;
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
  };

  const applyPatches = async (patches: RowPatch[]) => {
    if (!patches.length) {
      onMessage(t("feeds.noEdits"), "warning");
      return;
    }
    setSaving(true);
    try {
      const result = await withToken((token) =>
        patchFeedRows(token, patches, platforms, [country], true),
      );
      if (result.feeds?.length) {
        onApplied(
          result.feeds.map((u) => ({
            country: u.country || u.language || country,
            platform: u.platform || platform,
            url: u.url,
            csv_url: (u.url || "").replace(".xml", ".csv"),
            item_count: u.items || 0,
            updated_at: new Date().toISOString(),
          })),
        );
      } else {
        onApplied();
      }
      onMessage(result.message || t("feeds.applyOk"), "success");
      await load(offset, q);
    } catch (e) {
      onMessage(e instanceof Error ? e.message : String(e), "critical");
    } finally {
      setSaving(false);
    }
  };

  const applyEdits = async () => {
    const patches = Object.values(drafts)
      .map((d) => {
        const orig = items.find((i) => i.sku === d.sku);
        if (!orig) return null;
        return buildRowPatch(d, orig);
      })
      .filter(Boolean) as RowPatch[];
    await applyPatches(patches);
  };

  const applyOneRow = async (row: FeedPreviewItem) => {
    const patch = buildRowPatch(draftOf(row), row);
    if (!patch) {
      onMessage(t("feeds.noEdits"), "warning");
      return;
    }
    setSavingSku(row.sku);
    try {
      const result = await withToken((token) =>
        patchFeedRows(token, [patch], platforms, [country], true),
      );
      if (result.feeds?.length) {
        onApplied(
          result.feeds.map((u) => ({
            country: u.country || u.language || country,
            platform: u.platform || platform,
            url: u.url,
            csv_url: (u.url || "").replace(".xml", ".csv"),
            item_count: u.items || 0,
            updated_at: new Date().toISOString(),
          })),
        );
      } else {
        onApplied();
      }
      onMessage(result.message || t("feeds.rowSaved"), "success");
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[row.sku];
        return next;
      });
      await load(offset, q);
    } catch (e) {
      onMessage(e instanceof Error ? e.message : String(e), "critical");
    } finally {
      setSavingSku(null);
    }
  };

  const deleteOneRow = async (sku: string) => {
    if (!window.confirm(t("feeds.deleteRowConfirm"))) return;
    setDeletingSku(sku);
    try {
      const result = await withToken((token) =>
        deleteFeedRows(token, [sku], platforms, [country]),
      );
      if (result.url) {
        onApplied([
          {
            country,
            platform,
            url: result.url,
            csv_url: result.url.replace(".xml", ".csv"),
            item_count: result.item_count || 0,
            updated_at: new Date().toISOString(),
          },
        ]);
      } else {
        onApplied();
      }
      onMessage(result.message || t("feeds.rowDeleted"), "success");
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[sku];
        return next;
      });
      await load(offset, q);
    } catch (e) {
      onMessage(e instanceof Error ? e.message : String(e), "critical");
    } finally {
      setDeletingSku(null);
    }
  };

  const rowIsDirty = (row: FeedPreviewItem) =>
    Boolean(buildRowPatch(draftOf(row), row));

  const loadImages = async (sku: string) => {
    setImageSku(sku);
    try {
      const ctx = await withToken((token) =>
        fetchFeedImageCandidates(token, sku),
      );
      setImageCandidates(ctx.candidates || []);
    } catch (e) {
      onMessage(e instanceof Error ? e.message : String(e), "critical");
    }
  };

  const pickImage = (sku: string, url: string) => {
    setDrafts((prev) => {
      const base = prev[sku] || items.find((i) => i.sku === sku);
      if (!base) return prev;
      return { ...prev, [sku]: { ...base, image_url: url } };
    });
    setImageSku(null);
    setImageCandidates([]);
  };

  const onRestore = async (id: string) => {
    setSaving(true);
    try {
      const res = await withToken((token) => restoreFeedSnapshot(token, id));
      onMessage(t("feeds.restored"), "success");
      onApplied(
        res.url
          ? [
              {
                country,
                platform,
                url: res.url,
                csv_url: res.url.replace(".xml", ".csv"),
                item_count: res.item_count || 0,
                updated_at: new Date().toISOString(),
              },
            ]
          : undefined,
      );
      await load(0, q);
    } catch (e) {
      onMessage(e instanceof Error ? e.message : String(e), "critical");
    } finally {
      setSaving(false);
    }
  };

  const draftCount = Object.keys(drafts).length;

  const editorBody = (
        <s-box padding="base" border="base" borderRadius="base">
          <s-stack gap="base">
            <s-stack direction="inline" gap="small" alignItems="end">
              <s-text-field
                label={t("feeds.search")}
                value={q}
                onInput={(e: Event) =>
                  setQ((e.target as HTMLInputElement).value)
                }
              />
              <s-button
                variant="secondary"
                onClick={() => void load(0, q)}
                disabled={loading}
              >
                {t("feeds.searchBtn")}
              </s-button>
              {!isPage ? (
                <s-button
                  variant="primary"
                  onClick={() => void applyEdits()}
                  disabled={saving || !Object.keys(drafts).length}
                >
                  {saving ? t("feeds.applying") : t("feeds.applyEdits")}
                </s-button>
              ) : null}
            </s-stack>

            <s-text tone="neutral">
              {t("feeds.previewCount", {
                shown: items.length,
                total,
              })}
            </s-text>

            {loading ? (
              <s-text>{t("feeds.loading")}</s-text>
            ) : (
              <s-stack gap="base">
                {items.map((row) => {
                  const d = draftOf(row);
                  const dirty = rowIsDirty(row);
                  const rowBusy =
                    savingSku === row.sku || deletingSku === row.sku;
                  return (
                    <s-box
                      key={row.sku}
                      padding="base"
                      border="base"
                      borderRadius="base"
                    >
                      <div
                        style={{
                          display: "flex",
                          gap: 16,
                          alignItems: "flex-start",
                        }}
                      >
                        <div style={{ flex: 1, minWidth: 0 }}>
                      <s-stack gap="small">
                        <s-stack direction="inline" gap="base" alignItems="start">
                          {d.image_url ? (
                            <img
                              src={d.image_url}
                              alt=""
                              width={56}
                              height={56}
                              style={{
                                objectFit: "cover",
                                borderRadius: 6,
                              }}
                            />
                          ) : null}
                          <s-stack gap="small">
                            <s-text type="strong">{row.sku}</s-text>
                            {row.issue ? (
                              <s-badge tone="warning">{row.issue}</s-badge>
                            ) : null}
                            <s-text-field
                              label={t("feeds.colTitle")}
                              value={d.title}
                              onInput={(e: Event) =>
                                setDraftField(
                                  row.sku,
                                  "title",
                                  (e.target as HTMLInputElement).value,
                                )
                              }
                            />
                            <s-stack direction="inline" gap="small">
                              <s-text-field
                                label={t("feeds.colColor")}
                                value={d.color}
                                onInput={(e: Event) =>
                                  setDraftField(
                                    row.sku,
                                    "color",
                                    (e.target as HTMLInputElement).value,
                                  )
                                }
                              />
                              <s-text-field
                                label={t("feeds.colSize")}
                                value={d.size}
                                onInput={(e: Event) =>
                                  setDraftField(
                                    row.sku,
                                    "size",
                                    (e.target as HTMLInputElement).value,
                                  )
                                }
                              />
                            </s-stack>
                            <s-text tone="neutral">{d.price}</s-text>
                            <s-button
                              variant="secondary"
                              onClick={() => void loadImages(row.sku)}
                            >
                              {t("feeds.pickImage")}
                            </s-button>
                          </s-stack>
                        </s-stack>

                        {imageSku === row.sku && imageCandidates.length ? (
                          <s-stack direction="inline" gap="small">
                            {imageCandidates.slice(0, 8).map((c) => (
                              <s-button
                                key={c.url}
                                variant="secondary"
                                onClick={() => pickImage(row.sku, c.url)}
                              >
                                <img
                                  src={c.url}
                                  alt=""
                                  width={48}
                                  height={48}
                                  style={{ objectFit: "cover" }}
                                />
                              </s-button>
                            ))}
                          </s-stack>
                        ) : null}
                      </s-stack>
                        </div>
                        <s-stack gap="small">
                          <s-button
                            variant="primary"
                            disabled={rowBusy || !dirty}
                            onClick={() => void applyOneRow(row)}
                          >
                            {savingSku === row.sku
                              ? t("feeds.savingRow")
                              : t("feeds.saveRow")}
                          </s-button>
                          <s-button
                            variant="secondary"
                            tone="critical"
                            disabled={rowBusy || saving || Boolean(savingSku)}
                            onClick={() => void deleteOneRow(row.sku)}
                          >
                            {deletingSku === row.sku
                              ? t("feeds.deletingRow")
                              : t("feeds.deleteRow")}
                          </s-button>
                        </s-stack>
                      </div>
                    </s-box>
                  );
                })}
              </s-stack>
            )}

            <s-stack direction="inline" gap="small">
              <s-button
                variant="secondary"
                disabled={offset <= 0 || loading}
                onClick={() => void load(Math.max(0, offset - limit), q)}
              >
                {t("feeds.prev")}
              </s-button>
              <s-button
                variant="secondary"
                disabled={offset + limit >= total || loading}
                onClick={() => void load(offset + limit, q)}
              >
                {t("feeds.next")}
              </s-button>
            </s-stack>

            <s-stack gap="small">
              <s-text type="strong">{t("feeds.snapshots")}</s-text>
              <s-text tone="neutral">{t("feeds.snapshotsHelp")}</s-text>
              {!snapshots.length ? (
                <s-text tone="neutral">{t("feeds.noSnapshots")}</s-text>
              ) : (
                snapshots.map((s) => (
                  <s-stack
                    key={s.id}
                    direction="inline"
                    gap="small"
                    alignItems="center"
                  >
                    <s-text>
                      {s.created_at} · {s.item_count}
                    </s-text>
                    <s-button
                      variant="secondary"
                      disabled={saving}
                      onClick={() => void onRestore(s.id)}
                    >
                      {t("feeds.restore")}
                    </s-button>
                  </s-stack>
                ))
              )}
            </s-stack>
          </s-stack>
        </s-box>
  );

  if (isPage) {
    const marketLabel = t(`setup.country.${country}`);
    return (
      <s-stack gap="base">
        <s-stack direction="inline" gap="small" alignItems="center">
          <s-link href="/app">{t("feeds.backToWorkbench")}</s-link>
          <s-text tone="neutral">·</s-text>
          <s-text type="strong">
            {t("feeds.pageTitle", {
              platform: platform.toUpperCase(),
              market: marketLabel,
            })}
          </s-text>
        </s-stack>
        {feed.updated_at ? (
          <s-text tone="neutral">
            {t("feeds.pageMeta", {
              count: String(feed.item_count ?? total),
              updated: feed.updated_at,
            })}
          </s-text>
        ) : null}
        <s-stack direction="inline" gap="small">
          <s-button variant="secondary" onClick={() => void copyUrl(feed.url)}>
            {t("feeds.copyShort")}
          </s-button>
          <s-button variant="secondary" onClick={() => void downloadCsv()}>
            {t("feeds.downloadCsv")}
          </s-button>
          <s-button variant="tertiary" onClick={() => openXml()}>
            {t("feeds.openRawXml")}
          </s-button>
          <s-button
            variant="primary"
            onClick={() => void applyEdits()}
            disabled={saving || !draftCount}
          >
            {saving
              ? t("feeds.applying")
              : t("feeds.applyEditsWithCount", { n: draftCount })}
          </s-button>
        </s-stack>
        {editorBody}
      </s-stack>
    );
  }

  return (
    <s-stack gap="small">
      <s-stack direction="inline" gap="small">
        <s-button
          variant="secondary"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? t("feeds.hidePreview") : t("feeds.viewItems")}
        </s-button>
        <s-button variant="secondary" onClick={() => void copyUrl(feed.url)}>
          {t("feeds.copyShort")}
        </s-button>
        <s-button variant="secondary" onClick={() => void downloadCsv()}>
          {t("feeds.downloadCsv")}
        </s-button>
        <s-button variant="tertiary" onClick={() => openXml()}>
          {t("feeds.openRawXml")}
        </s-button>
      </s-stack>

      {open ? editorBody : null}
    </s-stack>
  );
}
