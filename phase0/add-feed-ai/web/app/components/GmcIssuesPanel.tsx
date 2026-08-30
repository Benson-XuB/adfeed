import { useCallback, useEffect, useState } from "react";
import { t } from "../lib/i18n";
import {
  disconnectGoogle,
  fetchGoogleIssues,
  fetchGoogleStatus,
  refreshGoogleMerchants,
  selectGoogleMerchant,
  startGoogleOAuth,
  syncGoogleIssues,
  type GmcIssueRow,
  type GoogleStatus,
} from "../lib/adfeed-api";
import styles from "./GmcIssuesPanel.module.css";

type Props = {
  getToken: () => Promise<string>;
};

export function GmcIssuesPanel({ getToken }: Props) {
  const [status, setStatus] = useState<GoogleStatus | null>(null);
  const [issues, setIssues] = useState<GmcIssueRow[]>([]);
  const [merchantId, setMerchantId] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [meta, setMeta] = useState<{ matched: number; unmatched: number }>({
    matched: 0,
    unmatched: 0,
  });

  const reload = useCallback(async () => {
    setErr("");
    try {
      const token = await getToken();
      const st = await fetchGoogleStatus(token);
      setStatus(st);
      const mid = st.selected_merchant_id || merchantId;
      if (mid) setMerchantId(mid);
      if (mid) {
        const res = await fetchGoogleIssues(token, mid);
        setIssues(res.issues || []);
        setMeta({ matched: res.matched, unmatched: res.unmatched });
      } else {
        setIssues([]);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [getToken, merchantId]);

  useEffect(() => {
    void reload();
  }, [getToken]); // eslint-disable-line react-hooks/exhaustive-deps

  const onConnect = async (ads: boolean) => {
    setBusy(true);
    setErr("");
    try {
      const token = await getToken();
      const { authorize_url } = await startGoogleOAuth(token, ads);
      window.open(authorize_url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onDisconnect = async () => {
    setBusy(true);
    setErr("");
    try {
      const token = await getToken();
      await disconnectGoogle(token);
      setMerchantId("");
      setIssues([]);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onRefreshMerchants = async () => {
    setBusy(true);
    setErr("");
    try {
      const token = await getToken();
      await refreshGoogleMerchants(token);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onSelectMerchant = async (mid: string) => {
    if (!mid) return;
    setBusy(true);
    try {
      const token = await getToken();
      await selectGoogleMerchant(token, mid);
      setMerchantId(mid);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onSync = async () => {
    if (!merchantId) return;
    setBusy(true);
    setErr("");
    try {
      const token = await getToken();
      await syncGoogleIssues(token, merchantId);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={styles.panel} aria-labelledby="gmc-issues-heading">
      <div className={styles.head}>
        <h2 id="gmc-issues-heading">{t("gmc.issuesTitle")}</h2>
        <p className={styles.hint}>{t("gmc.issuesHint")}</p>
      </div>

      {!status?.oauth_configured ? (
        <p className={styles.muted}>{t("gmc.oauthNotConfigured")}</p>
      ) : null}

      {status?.oauth_configured && !status?.connected ? (
        <div className={styles.toolbar}>
          <s-button variant="primary" disabled={busy} onClick={() => void onConnect(false)}>
            {t("gmc.connect")}
          </s-button>
        </div>
      ) : null}

      {status?.connected ? (
        <div className={styles.toolbar}>
          <label className={styles.label}>
            {t("gmc.merchant")}
            <select
              value={merchantId}
              disabled={busy}
              onChange={(e) => void onSelectMerchant(e.target.value)}
            >
              <option value="">{t("gmc.selectMerchant")}</option>
              {(status.merchants || []).map((m) => (
                <option key={m.merchant_id} value={m.merchant_id}>
                  {m.display_name || m.merchant_id}
                </option>
              ))}
            </select>
          </label>
          <s-button variant="secondary" disabled={busy} onClick={() => void onRefreshMerchants()}>
            {t("gmc.refreshMerchants")}
          </s-button>
          <s-button variant="secondary" disabled={busy || !merchantId} onClick={() => void onSync()}>
            {t("gmc.sync")}
          </s-button>
          <s-button variant="tertiary" disabled={busy} onClick={() => void onDisconnect()}>
            {t("gmc.disconnect")}
          </s-button>
        </div>
      ) : status?.oauth_configured ? null : (
        <p className={styles.muted}>{t("gmc.connectLater")}</p>
      )}

      {err ? <p className={styles.err}>{err}</p> : null}

      {issues.length > 0 ? (
        <>
          <p className={styles.meta}>
            {t("gmc.matchStats", {
              matched: String(meta.matched),
              unmatched: String(meta.unmatched),
            })}
          </p>
          <ul className={styles.list}>
            {issues.map((it) => (
              <li key={it.id || `${it.offer_id}-${it.reason_code}`}>
                <span className={styles.sku}>{it.offer_id}</span>
                <span className={styles.status}>{it.status}</span>
                <span className={styles.reason}>{it.reason_text || it.reason_code}</span>
                <span className={styles.action}>{it.suggested_action}</span>
                {!it.product_id_internal ? (
                  <span className={styles.unmatched}>{t("gmc.unmatched")}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className={styles.muted}>{t("gmc.empty")}</p>
      )}
    </section>
  );
}
