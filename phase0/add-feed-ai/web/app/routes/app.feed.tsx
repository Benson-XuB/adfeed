import { useCallback, useEffect, useMemo, useState } from "react";
import type { HeadersFunction, LoaderFunctionArgs } from "react-router";
import { useAppBridge } from "@shopify/app-bridge-react";
import { useSearchParams } from "react-router";
import { authenticate } from "../shopify.server";
import { boundary } from "@shopify/shopify-app-react-router/server";
import { t } from "../lib/i18n";
import { FeedPreviewPanel } from "../components/FeedPreviewPanel";
import {
  type FeedInfo,
  getFeedStatus,
} from "../lib/adfeed-api";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  return null;
};

export default function FeedEditorPage() {
  const shopify = useAppBridge();
  const [searchParams] = useSearchParams();
  const platform = (searchParams.get("platform") || "google").toLowerCase();
  const country = (searchParams.get("country") || "US").toUpperCase();

  const [busy, setBusy] = useState(true);
  const [feed, setFeed] = useState<FeedInfo | null>(null);
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState<
    "info" | "success" | "warning" | "critical"
  >("info");

  const withToken = useCallback(
    async <T,>(fn: (token: string) => Promise<T>) => {
      const token = await shopify.idToken();
      return fn(token);
    },
    [shopify],
  );

  const showMsg = (
    text: string,
    tone: "info" | "success" | "warning" | "critical" = "info",
  ) => {
    setMessage(text);
    setMessageTone(tone);
  };

  const loadFeed = useCallback(async () => {
    setBusy(true);
    try {
      const status = await withToken((token) => getFeedStatus(token));
      const match =
        status.feeds?.find(
          (f) =>
            (f.platform || "google").toLowerCase() === platform &&
            String(f.country || "").toUpperCase() === country,
        ) || null;
      setFeed(match);
      if (!match?.url) {
        showMsg(t("workbench.needGenerate"), "warning");
      }
    } catch (e) {
      showMsg(e instanceof Error ? e.message : String(e), "critical");
    } finally {
      setBusy(false);
    }
  }, [withToken, platform, country]);

  useEffect(() => {
    void loadFeed();
  }, [loadFeed]);

  const platforms = useMemo(() => [platform], [platform]);

  const copyUrl = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      showMsg(t("feeds.copied"), "success");
      setTimeout(() => showMsg(""), 2000);
    } catch {
      showMsg(t("feeds.copyFailed"), "critical");
    }
  };

  return (
    <s-page heading={t("feeds.editAllFeed")}>
      <s-link slot="breadcrumb-actions" href="/app">
        {t("feeds.backToWorkbench")}
      </s-link>

      {message ? (
        <s-banner tone={messageTone} onDismiss={() => showMsg("")}>
          <s-text>{message}</s-text>
        </s-banner>
      ) : null}

      {busy ? (
        <s-section>
          <s-text>{t("feeds.loading")}</s-text>
        </s-section>
      ) : feed?.url ? (
        <s-section>
          <FeedPreviewPanel
            mode="page"
            feed={feed}
            withToken={withToken}
            platforms={platforms}
            copyUrl={(url) => void copyUrl(url)}
            onMessage={showMsg}
            onApplied={() => void loadFeed()}
          />
        </s-section>
      ) : (
        <s-section>
          <s-stack gap="small">
            <s-text tone="neutral">{t("workbench.needGenerate")}</s-text>
            <s-link href="/app">{t("feeds.backToWorkbench")}</s-link>
          </s-stack>
        </s-section>
      )}
    </s-page>
  );
}

export const headers: HeadersFunction = (headersArgs) => {
  return boundary.headers(headersArgs);
};
