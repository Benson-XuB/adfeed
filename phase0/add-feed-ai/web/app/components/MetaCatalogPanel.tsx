import { useCallback, useEffect, useState } from "react";
import { t } from "../lib/i18n";
import {
  attachMetaFeed,
  disconnectMeta,
  fetchMetaIssues,
  fetchMetaStatus,
  refreshMetaCatalogs,
  selectMetaCatalog,
  startMetaOAuth,
  syncMetaIssues,
  type MetaStatus,
  type PlatformIssueRow,
} from "../lib/adfeed-api";
import styles from "./GmcIssuesPanel.module.css";

type Props = {
  getToken: () => Promise<string>;
  country?: string;
};

export function MetaCatalogPanel({ getToken, country = "US" }: Props) {
  const [status, setStatus] = useState<MetaStatus | null>(null);
  const [catalogId, setCatalogId] = useState("");
  const [issues, setIssues] = useState<PlatformIssueRow[]>([]);
  const [metaStats, setMetaStats] = useState({ matched: 0, unmatched: 0 });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const reload = useCallback(async () => {
    setErr("");
    try {
      const token = await getToken();
      const st = await fetchMetaStatus(token);
      setStatus(st);
      const cid = st.selected_catalog_id || catalogId;
      if (cid) setCatalogId(cid);
      if (cid) {
        const res = await fetchMetaIssues(token, cid);
        setIssues(res.issues || []);
        setMetaStats({ matched: res.matched, unmatched: res.unmatched });
      } else {
        setIssues([]);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [getToken, catalogId]);

  useEffect(() => {
    void reload();
  }, [getToken]); // eslint-disable-line react-hooks/exhaustive-deps

  const onConnect = async () => {
    setBusy(true);
    setErr("");
    try {
      const token = await getToken();
      const { authorize_url } = await startMetaOAuth(token);
      window.open(authorize_url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onDisconnect = async () => {
    setBusy(true);
    try {
      const token = await getToken();
      await disconnectMeta(token);
      setCatalogId("");
      setIssues([]);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onSelect = async (cid: string) => {
    if (!cid) return;
    setBusy(true);
    try {
      const token = await getToken();
      await selectMetaCatalog(token, cid);
      setCatalogId(cid);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onRefresh = async () => {
    setBusy(true);
    try {
      const token = await getToken();
      await refreshMetaCatalogs(token);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onAttach = async () => {
    if (!catalogId) return;
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      const token = await getToken();
      const res = await attachMetaFeed(token, catalogId, country);
      setMsg(t("meta.attachOk", { feedId: String(res.product_feed_id || "") }));
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onSyncIssues = async () => {
    if (!catalogId) return;
    setBusy(true);
    setErr("");
    try {
      const token = await getToken();
      await syncMetaIssues(token, catalogId);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={styles.panel} aria-labelledby="meta-catalog-heading">
      <div className={styles.head}>
        <h2 id="meta-catalog-heading">{t("meta.catalogTitle")}</h2>
        <p className={styles.hint}>{t("meta.catalogHint")}</p>
      </div>

      {!status?.oauth_configured ? (
        <p className={styles.muted}>{t("meta.oauthNotConfigured")}</p>
      ) : null}

      {status?.oauth_configured && !status.connected ? (
        <div className={styles.toolbar}>
          <s-button variant="primary" disabled={busy} onClick={() => void onConnect()}>
            {t("meta.connect")}
          </s-button>
        </div>
      ) : null}

      {status?.connected ? (
        <div className={styles.toolbar}>
          <label className={styles.label}>
            {t("meta.catalog")}
            <select
              value={catalogId}
              disabled={busy}
              onChange={(e) => void onSelect(e.target.value)}
            >
              <option value="">{t("meta.selectCatalog")}</option>
              {(status.catalogs || []).map((c) => (
                <option key={c.catalog_id} value={c.catalog_id}>
                  {c.display_name || c.catalog_id}
                </option>
              ))}
            </select>
          </label>
          <s-button variant="secondary" disabled={busy} onClick={() => void onRefresh()}>
            {t("meta.refreshCatalogs")}
          </s-button>
          <s-button
            variant="secondary"
            disabled={busy || !catalogId}
            onClick={() => void onAttach()}
          >
            {t("meta.attachFeed")}
          </s-button>
          <s-button
            variant="secondary"
            disabled={busy || !catalogId}
            onClick={() => void onSyncIssues()}
          >
            {t("meta.syncIssues")}
          </s-button>
          <s-button variant="tertiary" disabled={busy} onClick={() => void onDisconnect()}>
            {t("meta.disconnect")}
          </s-button>
        </div>
      ) : null}

      {err ? <p className={styles.err}>{err}</p> : null}
      {msg ? <p className={styles.meta}>{msg}</p> : null}

      {issues.length > 0 ? (
        <>
          <p className={styles.meta}>
            {t("meta.matchStats", {
              matched: String(metaStats.matched),
              unmatched: String(metaStats.unmatched),
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
                  <span className={styles.unmatched}>{t("meta.unmatched")}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      ) : status?.connected ? (
        <p className={styles.muted}>{t("meta.issuesEmpty")}</p>
      ) : null}
    </section>
  );
}
