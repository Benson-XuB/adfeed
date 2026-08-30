import { useCallback, useEffect, useState } from "react";
import { t } from "../lib/i18n";
import {
  fetchAdsMetrics,
  fetchGoogleStatus,
  startGoogleOAuth,
  syncAdsMetrics,
  type AdsMetricsRow,
  type GoogleStatus,
} from "../lib/adfeed-api";
import styles from "./GmcIssuesPanel.module.css";

type Props = {
  getToken: () => Promise<string>;
};

const CID_KEY = "adfeed.adsCustomerId";

export function AdsMetricsPanel({ getToken }: Props) {
  const [status, setStatus] = useState<GoogleStatus | null>(null);
  const [customerId, setCustomerId] = useState(() => {
    try {
      return localStorage.getItem(CID_KEY) || "";
    } catch {
      return "";
    }
  });
  const [rows, setRows] = useState<AdsMetricsRow[]>([]);
  const [degraded, setDegraded] = useState(false);
  const [productLevel, setProductLevel] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const reload = useCallback(async () => {
    setErr("");
    try {
      const token = await getToken();
      const st = await fetchGoogleStatus(token);
      setStatus(st);
      const cid = customerId.trim();
      if (cid) {
        const res = await fetchAdsMetrics(token, cid);
        setRows(res.rows || []);
        setDegraded(!!res.degraded);
        setProductLevel(res.product_level || 0);
      } else {
        setRows([]);
        setDegraded(false);
        setProductLevel(0);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [getToken, customerId]);

  useEffect(() => {
    void reload();
  }, [getToken]); // eslint-disable-line react-hooks/exhaustive-deps

  const onConnectAds = async () => {
    setBusy(true);
    setErr("");
    try {
      const token = await getToken();
      const { authorize_url } = await startGoogleOAuth(token, true);
      window.open(authorize_url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onSync = async () => {
    const cid = customerId.trim();
    if (!cid) return;
    try {
      localStorage.setItem(CID_KEY, cid);
    } catch {
      /* ignore */
    }
    setBusy(true);
    setErr("");
    try {
      const token = await getToken();
      await syncAdsMetrics(token, cid);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const microsToMoney = (micros: number) => (micros / 1_000_000).toFixed(2);

  return (
    <section className={styles.panel} aria-labelledby="ads-metrics-heading">
      <div className={styles.head}>
        <h2 id="ads-metrics-heading">{t("ads.metricsTitle")}</h2>
        <p className={styles.hint}>{t("ads.metricsHint")}</p>
      </div>

      {!status?.connected ? (
        <p className={styles.muted}>{t("ads.needGoogleFirst")}</p>
      ) : !status.has_ads_scope ? (
        <div className={styles.toolbar}>
          <s-button variant="secondary" disabled={busy} onClick={() => void onConnectAds()}>
            {t("ads.connectAds")}
          </s-button>
        </div>
      ) : (
        <div className={styles.toolbar}>
          <label className={styles.label}>
            {t("ads.customerId")}
            <input
              type="text"
              value={customerId}
              disabled={busy}
              placeholder="123-456-7890"
              onChange={(e) => setCustomerId(e.target.value)}
            />
          </label>
          <s-button
            variant="secondary"
            disabled={busy || !customerId.trim() || !status.ads_api_configured}
            onClick={() => void onSync()}
          >
            {t("ads.sync")}
          </s-button>
        </div>
      )}

      {status?.has_ads_scope && !status.ads_api_configured ? (
        <p className={styles.muted}>{t("ads.devTokenMissing")}</p>
      ) : null}

      {degraded ? <p className={styles.muted}>{t("ads.degraded")}</p> : null}
      {productLevel > 0 ? (
        <p className={styles.meta}>{t("ads.productLevel", { n: String(productLevel) })}</p>
      ) : null}

      {err ? <p className={styles.err}>{err}</p> : null}

      {rows.length > 0 ? (
        <ul className={styles.list}>
          {rows.slice(0, 50).map((r, i) => (
            <li key={`${r.date}-${r.offer_id || r.campaign_id || i}`}>
              <span className={styles.sku}>{r.offer_id || r.campaign_id || "—"}</span>
              <span className={styles.status}>{r.date}</span>
              <span className={styles.reason}>
                {t("ads.rowStats", {
                  imps: String(r.impressions),
                  clicks: String(r.clicks),
                  cost: microsToMoney(r.cost_micros),
                })}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className={styles.muted}>{t("ads.empty")}</p>
      )}
    </section>
  );
}
