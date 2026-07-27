"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import {
  getShopifyStatus, ShopifyStatus,
  getShopifyAuthUrl, getShopifyProducts, ShopifyProduct,
  processShopifyProducts, disconnectShopify,
} from "@/lib/api";

const COUNTRIES = [
  { code: "US", label: "United States" },
  { code: "DE", label: "Germany" },
  { code: "FR", label: "France" },
  { code: "ES", label: "Spain" },
  { code: "IT", label: "Italy" },
];

export default function ShopifyPage() {
  const { token } = useAuth();
  const router = useRouter();
  const [status, setStatus] = useState<ShopifyStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [shopInput, setShopInput] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [products, setProducts] = useState<ShopifyProduct[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [selectedCountries, setSelectedCountries] = useState<string[]>(["US"]);
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");
  const [totalCount, setTotalCount] = useState(0);
  const [nextPageInfo, setNextPageInfo] = useState<string | null>(null);

  // 检查连接状态
  const checkStatus = useCallback(async () => {
    if (!token) return;
    try {
      const s = await getShopifyStatus(token);
      setStatus(s);
    } catch { /* ignore */ }
    setLoading(false);
  }, [token]);

  useEffect(() => { checkStatus(); }, [checkStatus]);

  // 加载产品列表
  const loadProducts = useCallback(async (pageInfo?: string) => {
    if (!token) return;
    setLoadingProducts(true);
    try {
      const res = await getShopifyProducts(token, pageInfo, 50);
      setProducts(res.products);
      setTotalCount(res.total_count);
      setNextPageInfo(res.next_page_info);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load products");
    }
    setLoadingProducts(false);
  }, [token]);

  // 连接成功后加载产品
  useEffect(() => {
    if (status?.connected) {
      loadProducts();
    }
  }, [status?.connected, loadProducts]);

  // 连接 Shopify
  const handleConnect = async () => {
    if (!shopInput.trim() || !token) return;
    setConnecting(true);
    setError("");
    try {
      const { url } = await getShopifyAuthUrl(shopInput.trim(), token);
      // 在新窗口打开 Shopify 授权页面
      window.open(url, "_blank", "width=600,height=700");
      // 提示用户完成授权后刷新
      setTimeout(() => {
        checkStatus();
      }, 5000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get auth URL");
    }
    setConnecting(false);
  };

  // 断开连接
  const handleDisconnect = async () => {
    if (!token) return;
    try {
      await disconnectShopify(token);
      setStatus({ connected: false });
      setProducts([]);
      setSelectedIds(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to disconnect");
    }
  };

  // 选择/取消选择产品
  const toggleProduct = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // 全选/取消全选
  const toggleAll = () => {
    if (selectedIds.size === products.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(products.map(p => p.shopify_id)));
    }
  };

  // 选择国家
  const toggleCountry = (code: string) => {
    setSelectedCountries(prev =>
      prev.includes(code) ? prev.filter(c => c !== code) : [...prev, code]
    );
  };

  // 处理选中产品
  const handleProcess = async () => {
    if (!token || selectedIds.size === 0) return;
    setProcessing(true);
    setError("");
    try {
      const result = await processShopifyProducts(
        Array.from(selectedIds),
        selectedCountries,
        token
      );
      router.push(`/jobs/${result.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Processing failed");
    }
    setProcessing(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-6 h-6 border-2 border-stone-800 border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-black tracking-tight mb-2">Shopify</h1>
      <p className="text-sm text-stone-500 mb-6">
        Connect your Shopify store to import products and generate optimized ad feeds.
      </p>

      {error && <div className="mb-4 p-3 border border-red-200 bg-red-50 text-red-700 text-sm rounded">{error}</div>}

      {/* 未连接状态 */}
      {!status?.connected && (
        <div className="card py-12 text-center">
          <div className="text-4xl mb-4">⬡</div>
          <div className="font-bold text-lg mb-2">Connect your Shopify store</div>
          <p className="text-sm text-stone-500 mb-6">
            Enter your Shopify store domain to get started.
          </p>
          <div className="flex items-center gap-2 max-w-md mx-auto">
            <input
              type="text"
              value={shopInput}
              onChange={e => setShopInput(e.target.value)}
              placeholder="your-store"
              className="flex-1 px-3 py-2 border border-stone-200 rounded text-sm focus:outline-none focus:border-stone-400"
              onKeyDown={e => e.key === "Enter" && handleConnect()}
            />
            <span className="text-sm text-stone-400">.myshopify.com</span>
            <button
              onClick={handleConnect}
              disabled={connecting || !shopInput.trim()}
              className="btn px-6 py-2"
            >
              {connecting ? "Connecting..." : "Connect"}
            </button>
          </div>
        </div>
      )}

      {/* 已连接状态 */}
      {status?.connected && (
        <div className="space-y-6">
          {/* 店铺信息 */}
          <div className="card flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center text-green-700 font-bold">⬡</div>
              <div>
                <div className="font-bold">{status.shop_name}</div>
                <div className="text-xs text-stone-400">{status.shop_domain}</div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-green-600 font-medium">Connected</span>
              <button onClick={handleDisconnect} className="text-xs text-stone-400 hover:text-red-500 transition-colors">
                Disconnect
              </button>
            </div>
          </div>

          {/* 国家选择 */}
          <div>
            <div className="text-xs text-stone-400 tracking-widest uppercase mb-2">Target countries</div>
            <div className="flex flex-wrap gap-2">
              {COUNTRIES.map(({ code, label }) => (
                <button
                  key={code}
                  onClick={() => toggleCountry(code)}
                  className={`px-3 py-1.5 text-xs font-bold border-2 transition-colors ${
                    selectedCountries.includes(code)
                      ? "bg-stone-900 text-white border-stone-900"
                      : "border-stone-200 text-stone-500 hover:border-stone-400"
                  }`}
                >
                  {code} · {label}
                </button>
              ))}
            </div>
          </div>

          {/* 产品列表 */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs text-stone-400 tracking-widest uppercase">
                Products ({totalCount} total)
              </div>
              {products.length > 0 && (
                <button onClick={toggleAll} className="text-xs text-stone-500 hover:text-stone-700">
                  {selectedIds.size === products.length ? "Deselect all" : "Select all"}
                </button>
              )}
            </div>

            {loadingProducts ? (
              <div className="card py-12 text-center">
                <div className="w-6 h-6 border-2 border-stone-800 border-t-transparent animate-spin mx-auto mb-2" />
                <div className="text-sm text-stone-400">Loading products...</div>
              </div>
            ) : products.length === 0 ? (
              <div className="card py-12 text-center text-sm text-stone-400">
                No products found in your store.
              </div>
            ) : (
              <div className="space-y-2">
                {products.map(product => (
                  <div
                    key={product.shopify_id}
                    onClick={() => toggleProduct(product.shopify_id)}
                    className={`card flex items-center gap-4 cursor-pointer transition-colors ${
                      selectedIds.has(product.shopify_id)
                        ? "border-stone-900 bg-stone-50"
                        : "hover:border-stone-400"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.has(product.shopify_id)}
                      onChange={() => {}}
                      className="w-4 h-4 accent-stone-900"
                    />
                    {product.图片链接 && (
                      <img src={product.图片链接} alt="" className="w-12 h-12 object-cover rounded" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{product.标题}</div>
                      <div className="text-xs text-stone-400 mt-0.5">
                        {product.品牌}{product.品牌 && " · "}{product.分类}
                        {" · "}{product.variant_count} variants
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-sm font-bold">{product.price_range}</div>
                      <div className="text-xs text-stone-400">SKU: {product.SKU}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* 分页 */}
            {nextPageInfo && (
              <button
                onClick={() => loadProducts(nextPageInfo)}
                className="mt-3 text-sm text-stone-500 hover:text-stone-700 underline"
              >
                Load more products...
              </button>
            )}
          </div>

          {/* 操作按钮 */}
          {selectedIds.size > 0 && (
            <div className="card bg-stone-900 text-white flex items-center justify-between">
              <div>
                <span className="font-bold">{selectedIds.size}</span> products selected
                {" · "}{selectedCountries.join(", ")}
              </div>
              <button
                onClick={handleProcess}
                disabled={processing}
                className="px-6 py-2 bg-white text-stone-900 font-bold text-sm rounded hover:bg-stone-100 transition-colors"
              >
                {processing ? "Processing..." : `Generate Feed →`}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
