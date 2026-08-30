import { useCallback, useEffect, useState } from "react";
import { t } from "../lib/i18n";
import {
  attachTikTokFeed,
  disconnectTikTok,
  fetchTikTokStatus,
  refreshTikTokShops,
  selectTikTokShop,
  startTikTokOAuth,
  type TikTokStatus,
} from "../lib/adfeed-api";
import styles from "./GmcIssuesPanel.module.css";

type Props = {
  getToken: () => Promise<string>;
  country?: string;
};

export function TikTokShopPanel({ getToken, country = "US" }: Props) {
  const [status, setStatus] = useState<TikTokStatus | null>(null);
  const [shopId, setShopId] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const reload = useCallback(async () => {
    setErr("");
    try {
      const token = await getToken();
      const st = await fetchTikTokStatus(token);
      setStatus(st);
      const sid = st.selected_shop_id || shopId;
      if (sid) setShopId(sid);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [getToken, shopId]);

  useEffect(() => {
    void reload();
  }, [getToken]); // eslint-disable-line react-hooks/exhaustive-deps

  const onConnect = async () => {
    setBusy(true);
    setErr("");
    try {
      const token = await getToken();
      const { authorize_url } = await startTikTokOAuth(token);
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
      await disconnectTikTok(token);
      setShopId("");
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onSelect = async (sid: string) => {
    if (!sid) return;
    setBusy(true);
    try {
      const token = await getToken();
      await selectTikTokShop(token, sid);
      setShopId(sid);
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
      await refreshTikTokShops(token);
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onAttach = async () => {
    if (!shopId) return;
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      const token = await getToken();
      const res = await attachTikTokFeed(token, shopId, country);
      setMsg(t("tiktok.attachOk", { url: String(res.feed_url || "") }));
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={styles.panel} aria-labelledby="tiktok-shop-heading">
      <div className={styles.head}>
        <h2 id="tiktok-shop-heading">{t("tiktok.shopTitle")}</h2>
        <p className={styles.hint}>{t("tiktok.shopHint")}</p>
      </div>

      {!status?.oauth_configured ? (
        <p className={styles.muted}>{t("tiktok.oauthNotConfigured")}</p>
      ) : null}

      {status?.oauth_configured && !status.connected ? (
        <div className={styles.toolbar}>
          <s-button variant="primary" disabled={busy} onClick={() => void onConnect()}>
            {t("tiktok.connect")}
          </s-button>
        </div>
      ) : null}

      {status?.connected ? (
        <div className={styles.toolbar}>
          <label className={styles.label}>
            {t("tiktok.shop")}
            <select
              value={shopId}
              disabled={busy}
              onChange={(e) => void onSelect(e.target.value)}
            >
              <option value="">{t("tiktok.selectShop")}</option>
              {(status.shops || []).map((s) => (
                <option key={s.shop_id} value={s.shop_id}>
                  {s.display_name || s.shop_id}
                </option>
              ))}
            </select>
          </label>
          <s-button variant="secondary" disabled={busy} onClick={() => void onRefresh()}>
            {t("tiktok.refreshShops")}
          </s-button>
          <s-button
            variant="secondary"
            disabled={busy || !shopId}
            onClick={() => void onAttach()}
          >
            {t("tiktok.attachFeed")}
          </s-button>
          <s-button variant="tertiary" disabled={busy} onClick={() => void onDisconnect()}>
            {t("tiktok.disconnect")}
          </s-button>
        </div>
      ) : null}

      {err ? <p className={styles.err}>{err}</p> : null}
      {msg ? <p className={styles.meta}>{msg}</p> : null}
    </section>
  );
}
