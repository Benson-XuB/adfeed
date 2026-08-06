import { useState, useEffect, useCallback } from "preact/hooks";
import {
  fetchAllProducts,
  fetchBillingStatus,
  generateFeed,
  getFeedStatus,
  pollJob,
  estimateQuota,
} from "../../../../shared/models/products";

/** @typedef {import('../../../../shared/models/products').Product} Product */
/** @typedef {import('../../../../shared/models/products').FeedInfo} FeedInfo */
/** @typedef {import('../../../../shared/models/products').BillingStatus} BillingStatus */

const PLATFORMS = [
  { code: "google", label: "Google" },
  { code: "meta", label: "Meta" },
  { code: "tiktok", label: "TikTok" },
];

const LANGUAGES = [
  { code: "US", label: "US" },
  { code: "DE", label: "DE" },
  { code: "FR", label: "FR" },
  { code: "ES", label: "ES" },
  { code: "IT", label: "IT" },
];

export default function HomePage() {
  const [products, setProducts] = useState(/** @type {Product[]} */ ([]));
  const [selected, setSelected] = useState(/** @type {Set<string>} */ (new Set()));
  const [platforms, setPlatforms] = useState(/** @type {Set<string>} */ (new Set(["google"])));
  const [languages, setLanguages] = useState(/** @type {Set<string>} */ (new Set(["US"])));
  const [removeWatermarks, setRemoveWatermarks] = useState(false);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [feeds, setFeeds] = useState(/** @type {FeedInfo[]} */ ([]));
  const [message, setMessage] = useState("");
  const [filter, setFilter] = useState("");
  const [billing, setBilling] = useState(/** @type {BillingStatus | null} */ (null));
  const [estimate, setEstimate] = useState(0);

  useEffect(() => {
    (async () => {
      try {
        const [all, status] = await Promise.all([
          fetchAllProducts(),
          fetchBillingStatus().catch(() => null),
        ]);
        setProducts(all);
        if (status) setBilling(status);
        const activeIds = new Set(all.filter((p) => p.status === "ACTIVE").map((p) => p.id));
        setSelected(activeIds);
      } catch (e) {
        setMessage("加载产品失败: " + (e.message || e));
      }
      setLoading(false);
    })();
  }, []);

  const loadFeedStatus = useCallback(async () => {
    try {
      const list = await getFeedStatus();
      setFeeds(list);
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

  const toggleAll = () => {
    if (selected.size === products.length) setSelected(new Set());
    else setSelected(new Set(products.map((p) => p.id)));
  };

  const toggleProduct = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  const toggleInSet = (set, code, setter) => {
    const next = new Set(set);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    setter(next);
  };

  const handleGenerate = async () => {
    if (selected.size === 0) {
      setMessage("请至少选择一个产品");
      return;
    }
    if (platforms.size === 0 || languages.size === 0) {
      setMessage("请至少选择一个平台和一个市场");
      return;
    }
    if (billing && estimate > billing.quota_remaining) {
      setMessage(`配额不足：需要 ${estimate}，剩余 ${billing.quota_remaining}。请升级套餐。`);
      return;
    }

    setGenerating(true);
    setMessage("");

    try {
      const start = await generateFeed(
        Array.from(selected),
        Array.from(platforms),
        Array.from(languages),
        removeWatermarks,
      );
      setMessage(`任务已启动… 预计消耗 ${start.estimate ?? estimate} 配额`);
      const job = await pollJob(start.job_id);
      if (job.status === "failed") {
        throw new Error(job.error_msg || "生成失败");
      }
      const urls = job.result?.feeds || [];
      setMessage(`✅ 完成：${urls.length} 个 Feed URL`);
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
      } else {
        await loadFeedStatus();
      }
      const status = await fetchBillingStatus().catch(() => null);
      if (status) setBilling(status);
    } catch (e) {
      setMessage("生成失败: " + (e.message || e));
    }

    setGenerating(false);
  };

  const filtered = filter
    ? products.filter(
        (p) =>
          p.title.toLowerCase().includes(filter.toLowerCase()) ||
          p.productType.toLowerCase().includes(filter.toLowerCase()) ||
          p.vendor.toLowerCase().includes(filter.toLowerCase()),
      )
    : products;

  const totalVariants = products.reduce((sum, p) => sum + p.variantCount, 0);
  const quotaPct =
    billing && billing.quota_total > 0
      ? Math.min(100, Math.round((billing.quota_used / billing.quota_total) * 100))
      : 0;
  const affordable = !billing || estimate <= billing.quota_remaining;

  return (
    <s-page heading="AdFeed AI">
      <s-button
        slot="primary-action"
        variant="primary"
        disabled={generating || selected.size === 0 || !affordable}
        onClick={handleGenerate}
      >
        {generating ? "生成中..." : "生成 Feed"}
      </s-button>

      {billing && (
        <s-section heading="配额">
          <s-stack gap="small">
            <s-stack direction="inline" gap="small" alignItems="center">
              <s-badge>{billing.plan}</s-badge>
              <s-text>
                {billing.quota_used} / {billing.quota_total}（剩余 {billing.quota_remaining}）
              </s-text>
            </s-stack>
            <s-box background="subdued" borderRadius="rounded" overflow="hidden" inlineSize="100%" blockSize="8px">
              <s-box background="strong" inlineSize={`${quotaPct}%`} blockSize="100%" />
            </s-box>
            <s-text>
              预估消耗：{selected.size} SKU × {platforms.size} 平台 × {languages.size} 市场 ={" "}
              <s-text fontWeight="semibold">{estimate}</s-text>
              {!affordable && <s-text tone="critical"> — 配额不足，请升级</s-text>}
            </s-text>
          </s-stack>
        </s-section>
      )}

      {message && (
        <s-section>
          <s-banner
            tone={
              message.startsWith("✅")
                ? "success"
                : message.startsWith("生成失败") || message.includes("配额不足")
                  ? "critical"
                  : "info"
            }
          >
            <s-text>{message}</s-text>
          </s-banner>
        </s-section>
      )}

      {feeds.length > 0 && (
        <s-section heading="Feed 链接">
          <s-stack gap="small">
            {feeds.map((f) => (
              <s-box key={`${f.platform || "google"}-${f.country}`} padding="small" cornerRadius="rounded">
                <s-stack gap="small">
                  <s-stack direction="inline" gap="small" alignItems="center">
                    {f.platform && <s-badge>{f.platform}</s-badge>}
                    <s-badge tone="success">{f.country}</s-badge>
                    <s-text>{f.item_count} 个商品</s-text>
                  </s-stack>
                  <s-stack direction="inline" gap="small" alignItems="center">
                    <s-text size="small">{f.url}</s-text>
                    <s-button
                      variant="tertiary"
                      onClick={() => {
                        navigator.clipboard.writeText(f.url);
                        setMessage(`✅ URL 已复制`);
                        setTimeout(() => setMessage(""), 2000);
                      }}
                    >
                      复制
                    </s-button>
                  </s-stack>
                </s-stack>
              </s-box>
            ))}
          </s-stack>
        </s-section>
      )}

      <s-section heading="广告平台">
        <s-stack direction="inline" gap="small">
          {PLATFORMS.map((p) => (
            <s-checkbox
              key={p.code}
              checked={platforms.has(p.code)}
              onChange={() => toggleInSet(platforms, p.code, setPlatforms)}
              label={p.label}
            />
          ))}
        </s-stack>
      </s-section>

      <s-section heading="目标市场">
        <s-stack direction="inline" gap="small">
          {LANGUAGES.map((c) => (
            <s-checkbox
              key={c.code}
              checked={languages.has(c.code)}
              onChange={() => toggleInSet(languages, c.code, setLanguages)}
              label={c.label}
            />
          ))}
        </s-stack>
      </s-section>

      <s-section heading="选项">
        <s-checkbox
          checked={removeWatermarks}
          onChange={() => setRemoveWatermarks(!removeWatermarks)}
          label="去除图片水印（默认关闭）"
        />
      </s-section>

      {!loading && (
        <s-section
          padding="none"
          heading={`产品列表（已选 ${selected.size}/${products.length}，共 ${totalVariants} 个变体）`}
        >
          <s-box padding="small">
            <s-stack direction="inline" gap="small" alignItems="center">
              <s-text-field
                placeholder="搜索产品名称、类型、品牌..."
                value={filter}
                onInput={(e) => setFilter(e.target?.value || "")}
              />
              <s-button onClick={toggleAll} variant="tertiary">
                {selected.size === products.length ? "取消全选" : "全选"}
              </s-button>
            </s-stack>
          </s-box>

          <s-table>
            <s-table-header-row>
              <s-table-header style="width:40px"></s-table-header>
              <s-table-header>产品</s-table-header>
              <s-table-header>类型</s-table-header>
              <s-table-header>变体</s-table-header>
              <s-table-header>库存</s-table-header>
              <s-table-header>状态</s-table-header>
            </s-table-header-row>
            <s-table-body>
              {filtered.map((p) => (
                <s-table-row key={p.id}>
                  <s-table-cell>
                    <s-checkbox
                      checked={selected.has(p.id)}
                      onChange={() => toggleProduct(p.id)}
                      accessibilityLabel={`选择 ${p.title}`}
                    />
                  </s-table-cell>
                  <s-table-cell>
                    <s-stack direction="inline" gap="small" alignItems="center">
                      {p.image && (
                        <s-box as="img" src={p.image} alt={p.title} width="40px" height="40px" cornerRadius="rounded" />
                      )}
                      <s-stack gap="extra-small">
                        <s-text fontWeight="semibold">{p.title}</s-text>
                        <s-text tone="subdued" size="small">{p.vendor}</s-text>
                      </s-stack>
                    </s-stack>
                  </s-table-cell>
                  <s-table-cell>
                    <s-text>{p.productType || "—"}</s-text>
                  </s-table-cell>
                  <s-table-cell>
                    <s-badge tone="neutral">{p.variantCount}</s-badge>
                  </s-table-cell>
                  <s-table-cell>
                    <s-badge tone={p.totalInventory > 0 ? "success" : "critical"}>
                      {p.totalInventory > 0 ? `${p.totalInventory}` : "无库存"}
                    </s-badge>
                  </s-table-cell>
                  <s-table-cell>
                    <s-badge tone={p.status === "ACTIVE" ? "success" : "neutral"}>
                      {p.status === "ACTIVE" ? "在售" : p.status}
                    </s-badge>
                  </s-table-cell>
                </s-table-row>
              ))}
            </s-table-body>
          </s-table>
        </s-section>
      )}

      {loading && (
        <s-section>
          <s-stack alignItems="center" padding="large-400">
            <s-spinner />
            <s-text tone="subdued">正在加载产品...</s-text>
          </s-stack>
        </s-section>
      )}
    </s-page>
  );
}
