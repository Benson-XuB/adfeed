/**
 * Prefer rule_id / check id over raw API Chinese for App Home display.
 */
import { t } from "./i18n.js";

function looksMissing(translated, key) {
  if (!translated) return true;
  if (!key) return false;
  if (translated === key) return true;
  if (translated.startsWith("rules.") || translated.startsWith("complianceChecks.")) return true;
  return false;
}

/**
 * @param {any} e
 * @returns {{ message: string, suggestion: string }}
 */
export function formatQualityEvent(e) {
  const rid = String(e?.rule_id || "").toUpperCase();
  const after = String(e?.after ?? "");
  const before = String(e?.before ?? "");
  const level = String(e?.level || "").toUpperCase();
  const rawMsg = String(e?.message || "");
  const rawSug = String(e?.suggestion || "");

  const detail =
    (rid === "I03" &&
      (rawMsg.match(/（([^）]+)）/) || rawMsg.match(/\(([^)]+)\)/))?.[1]) ||
    after ||
    before ||
    "";

  const vars = { after, before, detail, value: after || before, id: rid };

  let msgKey = "";
  let sugKey = "";

  if (rid.startsWith("SEN")) {
    msgKey =
      level === "FATAL"
        ? "rules.SEN.block"
        : level === "WARN"
          ? "rules.SEN.flag"
          : "rules.SEN.soft";
    sugKey = "rules.SEN.sug";
  } else if (rid === "ID02") {
    msgKey = after ? "rules.ID02.msgReplaced" : "rules.ID02.msgWarn";
    sugKey = "rules.ID02.sug";
  } else if (rid === "VA01") {
    msgKey = after === "Multicolor" ? "rules.VA01.msgFallback" : "rules.VA01.msgClean";
    sugKey = "rules.VA01.sug";
  } else if (rid === "VA02") {
    msgKey =
      after === "One Size" && !before
        ? "rules.VA02.msgFallback"
        : "rules.VA02.msgClean";
    sugKey = "rules.VA02.sug";
  } else if (rid === "IMG02") {
    const empty = !before && !after && /空|empty/i.test(rawMsg);
    msgKey = empty ? "rules.IMG02.msgEmpty" : "rules.IMG02.msgFail";
    sugKey = empty ? "rules.IMG02.sugEmpty" : "rules.IMG02.sugFail";
  } else if (rid) {
    msgKey = `rules.${rid}.msg`;
    sugKey = `rules.${rid}.sug`;
  }

  let message = msgKey ? t(msgKey, vars) : rawMsg;
  if (looksMissing(message, msgKey)) message = rawMsg || message;

  let suggestion = "";
  if (sugKey) {
    suggestion = t(sugKey, vars);
    if (looksMissing(suggestion, sugKey)) suggestion = rawSug || "";
  } else {
    suggestion = rawSug;
  }

  return { message, suggestion };
}

const FOOT_POLICY = {
  FOOT_REFUND: "POL_REFUND",
  FOOT_PRIVACY: "POL_PRIVACY",
  FOOT_SHIPPING: "POL_SHIPPING",
  FOOT_TERMS: "POL_TERMS",
};

/**
 * @param {any} c
 * @returns {{ message: string, suggestion: string }}
 */
export function formatComplianceCheck(c) {
  const id = String(c?.id || "");
  const status = String(c?.status || "");
  const rawMsg = String(c?.message || "");
  const rawSug = String(c?.suggestion || "");

  const labelForPolicy = (polId) => t(`complianceChecks.policyLabel.${polId}`);

  let message = "";
  let suggestion = "";

  if (id.startsWith("POL_")) {
    const label = labelForPolicy(id);
    if (status === "fail") {
      message = t("complianceChecks.policyMissing", { label });
      suggestion = t("complianceChecks.policyMissingSug");
    } else if (status === "warn") {
      message = t("complianceChecks.policyWeak", { label });
      suggestion = t("complianceChecks.policyPresentSug");
    } else {
      message = t("complianceChecks.policyPresent", { label });
    }
  } else if (id === "SITE_HTTPS") {
    message = t(`complianceChecks.SITE_HTTPS.${status === "fail" ? "fail" : "pass"}`);
    suggestion = status === "fail" ? t("complianceChecks.SITE_HTTPS.failSug") : "";
  } else if (id === "SITE_REACHABLE") {
    if (status === "pass") {
      message = t("complianceChecks.SITE_REACHABLE.pass");
    } else {
      const code = (rawMsg.match(/HTTP\s+(\d+)/i) || [])[1];
      if (code) {
        message = t("complianceChecks.SITE_REACHABLE.http", { code });
        suggestion = t("complianceChecks.SITE_REACHABLE.httpSug");
      } else {
        message = t("complianceChecks.SITE_REACHABLE.down");
        suggestion = t("complianceChecks.SITE_REACHABLE.downSug");
      }
    }
  } else if (FOOT_POLICY[id]) {
    const label = labelForPolicy(FOOT_POLICY[id]);
    if (status === "pass") {
      message = t("complianceChecks.FOOT.pass", { label });
    } else if (status === "warn") {
      message = t("complianceChecks.FOOT.warn", { label });
      suggestion = t("complianceChecks.FOOT.warnSug");
    } else {
      message = t("complianceChecks.FOOT.fail", { label });
      suggestion = t("complianceChecks.FOOT.failSug");
    }
  } else if (id === "FOOT_CONTACT") {
    if (status === "pass") {
      message = t("complianceChecks.FOOT_CONTACT.pass");
    } else {
      message = t("complianceChecks.FOOT_CONTACT.warn");
      suggestion = t("complianceChecks.FOOT_CONTACT.warnSug");
    }
  } else if (id === "FOOT_SCAN") {
    message = t("complianceChecks.FOOT_SCAN.warn");
  } else if (id === "CONTACT_PAGE") {
    if (status === "pass") {
      message = t("complianceChecks.CONTACT_PAGE.pass");
    } else if (status === "warn") {
      message = t("complianceChecks.CONTACT_PAGE.warn");
      suggestion = t("complianceChecks.CONTACT_PAGE.warnSug");
    } else {
      message = t("complianceChecks.CONTACT_PAGE.fail");
      suggestion = t("complianceChecks.CONTACT_PAGE.failSug");
    }
  } else if (id.startsWith("CURR_")) {
    const country = id.slice(5);
    if (status === "pass") {
      message = t("complianceChecks.CURR.pass", { country });
    } else {
      message = t("complianceChecks.CURR.warn", { country });
      suggestion = t("complianceChecks.CURR.warnSug");
    }
  }

  if (!message || looksMissing(message, "complianceChecks")) {
    return { message: rawMsg, suggestion: rawSug };
  }
  return { message, suggestion: suggestion || "" };
}

export function qualityChecklistItems() {
  return [
    t("quality.checklist.shipping"),
    t("quality.checklist.claim"),
    t("quality.checklist.fatal"),
  ];
}
