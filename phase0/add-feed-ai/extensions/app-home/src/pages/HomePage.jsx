import { useState, useEffect, useCallback } from "preact/hooks";
import {
  fetchAllProducts,
  fetchBillingStatus,
  generateFeed,
  getFeedStatus,
} from "../../../../shared/models/products";

/** @typedef {import('../../../../shared/models/products').Product} Product */
/** @typedef {import('../../../../shared/models/products').FeedInfo} FeedInfo */
/** @typedef {import('../../../../shared/models/products').BillingStatus} BillingStatus */

const COUNTRIES = [
  { code: "US", label: "🇺🇸 美国" },
  { code: "DE", label: "🇩🇪 德国" },
  { code: "FR", label: "🇫🇷 法国" },
  { code: "ES", label: "🇪🇸 西班牙" },
  { code: "IT", label: "🇮🇹 意大利" },
];

export default function HomePage() {
  const [products, setProducts] = useState(/** @type {Product[]} */ ([]));
  const [selected, setSelected] = useState(/** @type {Set<string>} */ (new Set()));
  const [countries, setCountries] = useState(/** @type {Set<string>} */ (new Set(["US"])));
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [feeds, setFeeds] = useState(/** @type {FeedInfo[]} */ ([]));
  const [shopDomain, setShopDomain] = useState("");
  const [message, setMessage] = useState("");
  const [filter, setFilter] = useState("");
  const [billing, setBilling] = useState(/** @type {BillingStatus | null} */ (null));

  // 加载产品列表 + 配额
  useEffect(() => {
    (async () => {
      try {
        const [all, status] = await Promise.all([
          fetchAllProducts(),
          fetchBillingStatus().catch(() => null),
        ]);
        setProducts(all);
        if (status) setBilling(status);
        // 默认全选在售产品
        const activeIds = new Set(all.filter((p) => p.status === "ACTIVE").map((p) => p.id));
        setSelected(activeIds);
      } catch (e) {
        setMessage("加载产品失败: " + (e.message || e));
      }
      setLoading(false);
    })();
  }, []);

  // 获取 shop domain
  useEffect(() => {
    fetch("shopify:admin/api/2026-07/graphql.json", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: "{ shop { primaryDomain { url } } }" }),
    })
      .then((r) => r.json())
      .then((d) => {
        const url = d?.data?.shop?.primaryDomain?.url || "";
        setShopDomain(url.replace("https://", ""));
      })
      .catch(() => {});
  }, []);

  // 加载已有 Feed 状态
  const loadFeedStatus = useCallback(async () => {
    if (!shopDomain) return;
    try {
      const list = await getFeedStatus(shopDomain);
      setFeeds(list);
    } catch {
      // ignore
    }
  }, [shopDomain]);

  useEffect(() => {
    loadFeedStatus();
  }, [loadFeedStatus]);

  // 全选 / 取消全选
  const toggleAll = () => {
    if (selected.size === products.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(products.map((p) => p.id)));
    }
  };

  // 单个产品勾选
  const toggleProduct = (id) => {
    const next = new Set(selected);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setSelected(next);
  };

  // 国家选择
  const toggleCountry = (code) => {
    const next = new Set(countries);
    if (next.has(code)) {
      next.delete(code);
    } else {
      next.add(code);
    }
    setCountries(next);
  };

  // 生成 Feed
  const handleGenerate = async () => {
    if (selected.size === 0) {
      setMessage("请至少选择一个产品");
      return;
    }
    if (countries.size === 0) {
      setMessage("请至少选择一个目标国家");
      return;
    }

    setGenerating(true);
    setMessage("");

    try {
      await generateFeed(
        Array.from(selected),
        Array.from(countries),
        shopDomain,
      );
      setMessage(`✅ Feed 已生成！${selected.size} 个产品，${countries.size} 个国家`);
      await loadFeedStatus();
    } catch (e) {
      setMessage("生成失败: " + (e.message || e));
    }

    setGenerating(false);
  };

  // 过滤产品
  const filtered = filter
    ? products.filter(
        (p) =>
          p.title.toLowerCase().includes(filter.toLowerCase()) ||
          p.productType.toLowerCase().includes(filter.toLowerCase()) ||
          p.vendor.toLowerCase().includes(filter.toLowerCase()),
      )
    : products;

  // 库存统计
  const totalVariants = products.reduce((sum, p) => sum + p.variantCount, 0);

  const quotaPct =
    billing && billing.quota_total > 0
      ? Math.min(100, Math.round((billing.quota_used / billing.quota_total) * 100))
      : 0;

  return (
    <s-page heading="Google Shopping Feed">
      {/* 生成按钮 */}
      <s-button
        slot="primary-action"
        variant="primary"
        disabled={generating || selected.size === 0}
        onClick={handleGenerate}
      >
        {generating ? "生成中..." : feeds.length > 0 ? "刷新 Feed" : "生成 Feed"}
      </s-button>

      {/* 配额 */}
      {billing && (
        <s-section heading="配额">
          <s-stack gap="small">
            <s-stack direction="inline" gap="small" alignItems="center">
              <s-badge>{billing.plan}</s-badge>
              <s-text>
                {billing.quota_used} / {billing.quota_total} 已用（剩余 {billing.quota_remaining}）
              </s-text>
            </s-stack>
            <s-box
              background="subdued"
              borderRadius="rounded"
              overflow="hidden"
              inlineSize="100%"
              blockSize="8px"
            >
              <s-box
                background="strong"
                inlineSize={`${quotaPct}%`}
                blockSize="100%"
              />
            </s-box>
          </s-stack>
        </s-section>
      )}

      {/* 消息提示 */}
      {message && (
        <s-section>
          <s-banner tone={message.startsWith("✅") ? "success" : message.startsWith("生成失败") || message.startsWith("加载失败") ? "critical" : "info"}>
            <s-text>{message}</s-text>
          </s-banner>
        </s-section>
      )}

      {/* Feed 状态 */}
      {feeds.length > 0 && (
        <s-section heading="📡 Feed 链接（填入 GMC 即可）">
          <s-stack gap="small">
            {feeds.map((f) => (
              <s-box key={f.country} padding="small" cornerRadius="rounded">
                <s-stack gap="small">
                  <s-stack direction="inline" gap="small" alignItems="center">
                    <s-badge tone="success">{f.country}</s-badge>
                    <s-text>{f.item_count} 个商品</s-text>
                    {f.updated_at && (
                      <s-text size="small">
                        更新于 {new Date(f.updated_at).toLocaleString()}
                      </s-text>
                    )}
                  </s-stack>
                  <s-stack direction="inline" gap="small" alignItems="center">
                    <s-text size="small">
                      {f.url}
                    </s-text>
                    <s-button
                      variant="tertiary"
                      onClick={() => {
                        navigator.clipboard.writeText(f.url);
                        setMessage(`✅ ${f.country} Feed URL 已复制`);
                        setTimeout(() => setMessage(""), 2000);
                      }}
                    >
                      复制 XML
                    </s-button>
                    <s-button
                      variant="tertiary"
                      onClick={() => {
                        navigator.clipboard.writeText(f.csv_url);
                        setMessage(`✅ ${f.country} CSV URL 已复制`);
                        setTimeout(() => setMessage(""), 2000);
                      }}
                    >
                      复制 CSV
                    </s-button>
                  </s-stack>
                </s-stack>
              </s-box>
            ))}
          </s-stack>
        </s-section>
      )}

      {/* 筛选 & 国家选择 */}
      <s-section heading="🎯 目标市场">
        <s-stack direction="inline" gap="small">
          {COUNTRIES.map((c) => (
            <s-checkbox
              key={c.code}
              checked={countries.has(c.code)}
              onChange={() => toggleCountry(c.code)}
              label={c.label}
            />
          ))}
        </s-stack>
      </s-section>

      {/* 产品列表 */}
      {!loading && (
        <s-section padding="none" heading={`📦 产品列表（已选 ${selected.size}/${products.length}，共 ${totalVariants} 个变体）`}>
          {/* 搜索框 */}
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

          {/* 产品表格 */}
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
                        <s-box
                          as="img"
                          src={p.image}
                          alt={p.title}
                          width="40px"
                          height="40px"
                          cornerRadius="rounded"
                        />
                      )}
                      <s-stack gap="extra-small">
                        <s-text fontWeight="semibold">{p.title}</s-text>
                        <s-text tone="subdued" size="small">
                          {p.vendor}
                        </s-text>
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
                    <s-badge
                      tone={
                        p.status === "ACTIVE"
                          ? "success"
                          : p.status === "DRAFT"
                          ? "attention"
                          : "neutral"
                      }
                    >
                      {p.status === "ACTIVE" ? "在售" : p.status === "DRAFT" ? "草稿" : p.status}
                    </s-badge>
                  </s-table-cell>
                </s-table-row>
              ))}
            </s-table-body>
          </s-table>

          {filtered.length === 0 && (
            <s-box padding="large-400">
              <s-stack alignItems="center">
                <s-heading>没有找到产品</s-heading>
                <s-paragraph>
                  {filter ? "尝试修改搜索关键词" : "店铺暂无产品"}
                </s-paragraph>
              </s-stack>
            </s-box>
          )}
        </s-section>
      )}

      {/* 加载中 */}
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
