import { useCallback, useEffect, useState } from "react";
import { t } from "../lib/i18n";
import {
  disconnectGoogle,
  fetchGoogleIssues,
  fetchGoogleStatus,
  listGoogleDataSources,
  pushGoogleProducts,
  refreshGoogleMerchants,
  selectGoogleDataSource,
  selectGoogleMerchant,
  startGoogleOAuth,
  syncGoogleIssues,
  type GoogleDataSource,
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
  const [dataSources, setDataSources] = useState<GoogleDataSource[]>([]);
  const [dataSourceName, setDataSourceName] = useState("");
  const [busy, setBusy] = useState(false);
  const [pushBusy, setPushBusy] = useState(false);
  const [err, setErr] = useState("");
  const [pushMsg, setPushMsg] = useState("");
  const [meta, setMeta] = useState<{ matched: number; unmatched: number }>({
    matched: 0,
    unmatched: 0,
  });

  const loadDataSources = useCallback(
    async (token: string, mid: string, preferName = "") => {
      if (!mid) {
        setDataSources([]);
        setDataSourceName("");
        return;
      }
      try {
        const res = await listGoogleDataSources(token, mid);
        const list = res.data_sources || [];
        setDataSources(list);
        const savedOk =
          Boolean(preferName) && list.some((d) => d.name === preferName);
        const pick = savedOk ? preferName : list[0]?.name || "";
        setDataSourceName(pick);
        if (pick && !savedOk) {
          try {
            await selectGoogleDataSource(token, pick, mid);
          } catch {
            /* keep UI selection; push will surface API error */
          }
        }
      } catch {
        setDataSources([]);
        /* non-fatal — push still shows API errors */
      }
    },
    [],
  );

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
        const selectedMerchant = (st.merchants || []).find(
          (m) => m.merchant_id === mid,
        );
        const savedDs = (selectedMerchant?.data_source_name || "").trim();
        if (savedDs) setDataSourceName(savedDs);
        if (st.connected && st.push_enabled) {
          await loadDataSources(token, mid, savedDs);
        }
      } else {
        setIssues([]);
        setDataSources([]);
        setDataSourceName("");
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [getToken, merchantId, loadDataSources]);

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
      setDataSources([]);
      setDataSourceName("");
      setPushMsg("");
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

  const onSelectDataSource = async (name: string) => {
    if (!name || !merchantId) return;
    setBusy(true);
    setErr("");
    try {
      const token = await getToken();
      await selectGoogleDataSource(token, name, merchantId);
      setDataSourceName(name);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onRefreshDataSources = async () => {
    if (!merchantId) return;
    setBusy(true);
    setErr("");
    try {
      const token = await getToken();
      await loadDataSources(token, merchantId, dataSourceName);
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

  const onPushSandbox = async () => {
    setPushBusy(true);
    setErr("");
    setPushMsg("");
    try {
      if (!merchantId) {
        setErr(t("gmc.pushNeedMerchant"));
        return;
      }
      if (!dataSourceName) {
        setErr(t("gmc.pushNeedDataSource"));
        return;
      }
      const token = await getToken();
      // Task 6: omit rows — API returns 400 until Task 7 builds catalog from store.
      const run = await pushGoogleProducts(token, {
        merchant_id: merchantId,
      });
      setPushMsg(
        t("gmc.pushOk", {
          ok: String(run.ok_count ?? 0),
          fail: String(run.fail_count ?? 0),
        }),
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setPushBusy(false);
    }
  };

  const pushEnabled = Boolean(status?.push_enabled);
  const canPush =
    pushEnabled && Boolean(merchantId) && Boolean(dataSourceName) && !pushBusy;

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

      {status?.connected ? (
        <div className={styles.sandbox}>
          <div className={styles.head}>
            <h3 className={styles.sandboxTitle}>{t("gmc.sandboxTitle")}</h3>
            <p className={styles.hint}>{t("gmc.sandboxHint")}</p>
          </div>
          {!pushEnabled ? (
            <p className={styles.muted}>{t("gmc.pushDisabled")}</p>
          ) : (
            <div className={styles.toolbar}>
              <label className={styles.label}>
                {t("gmc.dataSource")}
                <select
                  value={dataSourceName}
                  disabled={busy || pushBusy || !merchantId}
                  onChange={(e) => void onSelectDataSource(e.target.value)}
                >
                  <option value="">{t("gmc.selectDataSource")}</option>
                  {dataSources.map((ds) => (
                    <option key={ds.name} value={ds.name}>
                      {ds.displayName || ds.name}
                    </option>
                  ))}
                </select>
              </label>
              <s-button
                variant="secondary"
                disabled={busy || pushBusy || !merchantId}
                onClick={() => void onRefreshDataSources()}
              >
                {t("gmc.refreshDataSources")}
              </s-button>
              <s-button
                variant="primary"
                disabled={!canPush || busy}
                onClick={() => void onPushSandbox()}
              >
                {pushBusy ? t("gmc.pushRunning") : t("gmc.pushSandbox")}
              </s-button>
            </div>
          )}
          {pushMsg ? <p className={styles.ok}>{pushMsg}</p> : null}
        </div>
      ) : null}

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
