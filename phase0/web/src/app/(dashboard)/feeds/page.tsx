"use client";

import { useAuth } from "@/lib/auth";
import { listFeeds, downloadFeed, FeedInfo } from "@/lib/api";
import { useEffect, useState, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const FLAGS: Record<string, string> = {
  US: "🇺🇸",
  DE: "🇩🇪",
  FR: "🇫🇷",
  ES: "🇪🇸",
  IT: "🇮🇹",
};

const NAMES: Record<string, string> = {
  US: "United States",
  DE: "Germany",
  FR: "France",
  ES: "Spain",
  IT: "Italy",
};

export default function FeedsPage() {
  const { token } = useAuth();
  const [feeds, setFeeds] = useState<FeedInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!token) return;
    try {
      const { feeds: f } = await listFeeds(token);
      setFeeds(f);
    } catch { /* ignore */ }
    setLoading(false);
  }, [token]);

  useEffect(() => { fetch(); }, [fetch]);

  const handleDownload = async (country: string) => {
    if (!token) return;
    setDownloading(country);
    try {
      const xml = await downloadFeed(country, token);
      const blob = new Blob([xml], { type: "application/xml" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `feed_${country.toLowerCase()}.xml`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
    setDownloading(null);
  };

  return (
    <div>
      <h1 className="text-2xl font-black tracking-tight mb-2">Feeds</h1>
      <p className="text-sm text-stone-500 mb-8">
        Google Merchant Center compatible XML feeds for your target countries.
      </p>

      {loading ? (
        <div className="text-sm text-stone-400">Loading...</div>
      ) : feeds.length === 0 ? (
        <div className="card text-center text-sm text-stone-400 py-12">
          No feeds generated yet. <a href="/upload" className="underline text-stone-700">Upload and process a file first.</a>
        </div>
      ) : (
        <div className="space-y-3">
          {feeds.map((f) => (
            <div key={f.country} className="card flex items-center justify-between">
              <div className="flex items-center gap-4">
                <span className="text-2xl">{FLAGS[f.country] || f.country}</span>
                <div>
                  <div className="font-bold text-sm">{NAMES[f.country] || f.country}</div>
                  <div className="text-xs text-stone-400">
                    {(f.size_bytes / 1024).toFixed(1)} KB · Updated {new Date(f.updated_at).toLocaleDateString()}
                  </div>
                </div>
              </div>
              <button
                onClick={() => handleDownload(f.country)}
                disabled={downloading === f.country}
                className="btn btn-sm"
              >
                {downloading === f.country ? "Downloading..." : "Download · XML"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
