import { useCallback, useEffect, useState } from "react";
import { t } from "../lib/i18n";
import {
  fetchAdsMetrics,
  fetchAdsSettings,
  fetchGoogleStatus,
  startGoogleOAuth,
  syncAdsMetrics,
  type AdsMetricsRow,
  type AdsMetricsSummary,
  type GoogleStatus,
} from "../lib/adfeed-api";
import styles from "./GmcIssuesPanel.module.css";

type Props = {
  getToken: () => Promise<string>;
};

const CID_KEY = "adfeed.adsCustomerId";
const emptySummary: AdsMetricsSummary = {
  impressions: 0,
  clicks: 0,
  cost_micros: 0,
  conversions: 0,
};

export function AdsMetricsPanel({ getToken }: Props) {
  const [status, setStatus] = useState<GoogleStatus | null>(null);
  const [customerId, setCustomerId] = useState(() => {
    try {
      return localStorage.getItem(CID_KEY) || "";
    } catch {
      return "";
    }
  });
  const [windowDays, setWindowDays] = useState<7 | 30>(7);
  const [rows, setRows] = useState<AdsMetricsRow[]>([]);
  const [summary, setSummary] = useState<AdsMetricsSummary>(emptySummary);
  const [degraded, setDegraded] = useState(false);
  const [productLevel, setProductLevel] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [settingsLoaded, setSettingsLoaded] = useState(false);

  const reload = useCallback(async () => {
    setErr("");
    try {
      const token = await getToken();
      const st = await fetchGoogleStatus(token);
      setStatus(st);

      let cid = customerId.trim();
      let wd: 7 | 30 = windowDays;
      if (!settingsLoaded) {
        try {
          const settings = await fetchAdsSettings(token);
          if (settings.ads_customer_id) {
            cid = String(settings.ads_customer_id);
            setCustomerId(cid);
            try {
              localStorage.setItem(CID_KEY, cid);
            } catch {
              /* ignore */
            }
          } else if (st.ads_customer_id) {
            cid = String(st.ads_customer_id);
            setCustomerId(cid);
          }
          const savedWd = settings.window_days === 30 || st.ads_window_days === 30 ? 30 : 7;
          wd = savedWd;
          setWindowDays(savedWd);
        } catch {
          /* settings optional on first load */
        }
        setSettingsLoaded(true);
      }

      if (cid) {
        const res = await fetchAdsMetrics(token, cid, wd);
        setRows(res.rows || []);
        setDegraded(!!res.degraded);
        setProductLevel(res.product_level || 0);
        setSummary(res.summary || emptySummary);
      } else {
        setRows([]);
        setDegraded(false);
        setProductLevel(0);
        setSummary(emptySummary);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [getToken, customerId, windowDays, settingsLoaded]);

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
      await syncAdsMetrics(token, cid, windowDays);
      setSettingsLoaded(true);
      const res = await fetchAdsMetrics(token, cid, windowDays);
      setRows(res.rows || []);
      setDegraded(!!res.degraded);
      setProductLevel(res.product_level || 0);
      setSummary(res.summary || emptySummary);
      const st = await fetchGoogleStatus(token);
      setStatus(st);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onToggleWindow = async (next: 7 | 30) => {
    if (next === windowDays) return;
    setWindowDays(next);
    const cid = customerId.trim();
    if (!cid) return;
    setBusy(true);
    setErr("");
    try {
      const token = await getToken();
      const res = await fetchAdsMetrics(token, cid, next);
      setRows(res.rows || []);
      setDegraded(!!res.degraded);
      setProductLevel(res.product_level || 0);
      setSummary(res.summary || emptySummary);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const scrollToGmcIssues = () => {
    document.getElementById("gmc-issues-heading")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
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
          <div className={styles.windowToggle} role="group" aria-label={t("ads.windowLabel")}>
            <button
              type="button"
              className={windowDays === 7 ? styles.windowActive : styles.windowBtn}
              disabled={busy}
              onClick={() => void onToggleWindow(7)}
            >
              {t("ads.window7")}
            </button>
            <button
              type="button"
              className={windowDays === 30 ? styles.windowActive : styles.windowBtn}
              disabled={busy}
              onClick={() => void onToggleWindow(30)}
            >
              {t("ads.window30")}
            </button>
          </div>
          <s-button
            variant="secondary"
            disabled={busy || !customerId.trim() || !status.ads_api_configured}
            onClick={() => void onSync()}
          >
            {t("ads.sync")}
          </s-button>
          <s-button variant="tertiary" disabled={busy} onClick={scrollToGmcIssues}>
            {t("ads.linkGmcIssues")}
          </s-button>
        </div>
      )}

      {status?.has_ads_scope && !status.ads_api_configured ? (
        <p className={styles.muted}>{t("ads.devTokenMissing")}</p>
      ) : null}

      {rows.length > 0 || summary.impressions > 0 || summary.clicks > 0 ? (
        <div className={styles.summaryStrip} aria-label={t("ads.summaryLabel")}>
          <span>
            {t("ads.summaryImps", { n: String(summary.impressions) })}
          </span>
          <span>
            {t("ads.summaryClicks", { n: String(summary.clicks) })}
          </span>
          <span>
            {t("ads.summaryCost", { n: microsToMoney(summary.cost_micros) })}
          </span>
          <span>
            {t("ads.summaryConv", { n: String(summary.conversions) })}
          </span>
        </div>
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
