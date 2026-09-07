import { useCallback, useEffect, useState } from "react";
import {
  fetchGoogleAccounts,
  fetchGoogleAuthorizeUrl,
  fetchGoogleMcStatus,
  pushFeedToGoogle,
  selectGoogleMerchant,
  type GoogleMcAccount,
  type GoogleMcStatus,
  type GooglePushResult,
} from "../lib/adfeed-api";
import styles from "./FeedWorkbench.module.css";

type Props = {
  country: string;
  feedReady: boolean;
  withToken: <T>(fn: (token: string) => Promise<T>) => Promise<T>;
  onMessage: (
    text: string,
    tone?: "info" | "success" | "warning" | "critical",
  ) => void;
};

export function GooglePushPanel({
  country,
  feedReady,
  withToken,
  onMessage,
}: Props) {
  const [status, setStatus] = useState<GoogleMcStatus | null>(null);
  const [accounts, setAccounts] = useState<GoogleMcAccount[]>([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<GooglePushResult | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await withToken((tok) => fetchGoogleMcStatus(tok));
      setStatus(s);
      if (s.connected && !s.merchant_id) {
        const list = await withToken((tok) => fetchGoogleAccounts(tok));
        setAccounts(list);
      }
    } catch (e) {
      onMessage(e instanceof Error ? e.message : "Google status failed", "warning");
    }
  }, [withToken, onMessage]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const connect = async () => {
    setBusy(true);
    try {
      const url = await withToken((tok) => fetchGoogleAuthorizeUrl(tok));
      window.open(url, "_top");
    } catch (e) {
      onMessage(e instanceof Error ? e.message : "Connect failed", "critical");
    } finally {
      setBusy(false);
    }
  };

  const pickMerchant = async (merchantId: string) => {
    setBusy(true);
    try {
      await withToken((tok) => selectGoogleMerchant(tok, merchantId));
      onMessage("Merchant linked. Ready to push.", "success");
      await refresh();
    } catch (e) {
      onMessage(e instanceof Error ? e.message : "Select merchant failed", "critical");
    } finally {
      setBusy(false);
    }
  };

  const push = async () => {
    if (!feedReady || busy) return;
    setBusy(true);
    setResult(null);
    try {
      const res = await withToken((tok) =>
        pushFeedToGoogle(tok, { country: country || "US" }),
      );
      setResult(res);
      const msg = `Pushed: ${res.success_count} ok, ${res.failure_count} failed. Approval not guaranteed.`;
      onMessage(msg, res.failure_count ? "warning" : "success");
      await refresh();
    } catch (e) {
      onMessage(e instanceof Error ? e.message : "Push failed", "critical");
    } finally {
      setBusy(false);
    }
  };

  const ready =
    Boolean(status?.connected) && Boolean(status?.merchant_id) && feedReady;

  return (
    <div className={styles.feedCard} style={{ marginBottom: 12 }}>
      <div style={{ fontWeight: 600, marginBottom: 8 }}>Push to Google</div>
      <p style={{ margin: "0 0 10px", fontSize: 13, opacity: 0.85 }}>
        Submit your reviewed feed into Merchant Center (API). Does not guarantee
        Google approval.
      </p>

      {!status?.configured ? (
        <s-text tone="caution">Google OAuth is not configured on the server.</s-text>
      ) : !status?.connected ? (
        <button
          type="button"
          className={styles.feedActionPrimary}
          disabled={busy}
          onClick={() => void connect()}
        >
          {busy ? "…" : "Connect Google"}
        </button>
      ) : !status.merchant_id ? (
        <div style={{ display: "grid", gap: 6 }}>
          <s-text>Select Merchant Center account</s-text>
          {accounts.map((a) => (
            <button
              key={a.merchant_id}
              type="button"
              className={styles.feedActionSecondary}
              disabled={busy}
              onClick={() => void pickMerchant(a.merchant_id)}
            >
              {a.display_name} ({a.merchant_id})
            </button>
          ))}
        </div>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          <s-text tone="success">
            MC {status.merchant_id}
            {status.data_source_name ? ` · ${status.data_source_name}` : ""}
          </s-text>
          <button
            type="button"
            className={styles.feedActionPrimary}
            disabled={!ready || busy}
            onClick={() => void push()}
          >
            {busy ? "Pushing…" : "Push to Google"}
          </button>
          {!feedReady ? (
            <s-text tone="neutral">Generate a feed first.</s-text>
          ) : null}
        </div>
      )}

      {result ? (
        <div style={{ marginTop: 10, fontSize: 13 }}>
          <div>
            Result: {result.success_count} ok / {result.failure_count} failed
            {result.item_attempted != null
              ? ` (of ${result.item_attempted})`
              : ""}
          </div>
          {result.merchant_center_url ? (
            <a
              href={result.merchant_center_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open Merchant Center
            </a>
          ) : null}
          {result.failures?.slice(0, 3).map((f) => (
            <div key={f.offer_id} style={{ opacity: 0.8 }}>
              {f.offer_id}: {f.error}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
