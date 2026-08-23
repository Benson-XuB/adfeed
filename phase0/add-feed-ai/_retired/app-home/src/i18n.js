/**
 * App Home UI language follows Shopify admin locale:
 * zh* → Simplified Chinese; everything else → English (default).
 * Not tied to feed target markets (US/DE/…).
 */
import { messages } from "./i18n-messages.js";

/** @returns {"en"|"zh-CN"} */
export function getAdminLocale() {
  let raw = "en";
  try {
    raw =
      (typeof shopify !== "undefined" &&
        (shopify.locale || shopify.i18n?.locale || shopify.i18n?.language)) ||
      (typeof navigator !== "undefined" && navigator.language) ||
      "en";
  } catch {
    /* ignore */
  }
  return String(raw || "en").toLowerCase().startsWith("zh") ? "zh-CN" : "en";
}

function dig(obj, key) {
  return String(key)
    .split(".")
    .reduce((acc, part) => (acc == null ? undefined : acc[part]), obj);
}

function fill(str, vars) {
  return String(str).replace(/\{\{(\w+)\}\}/g, (_, k) =>
    vars[k] != null ? String(vars[k]) : `{{${k}}}`,
  );
}

/**
 * @param {string} key
 * @param {Record<string, string|number|undefined>} [vars]
 */
export function t(key, vars = {}) {
  try {
    const i18n = typeof shopify !== "undefined" ? shopify.i18n : null;
    if (i18n && typeof i18n.translate === "function") {
      const out = i18n.translate(key, vars);
      // Shopify returns "MISSING KEY for locale…" when locale JSON lacks the key —
      // treat that as a miss and fall through to our catalogs.
      if (
        typeof out === "string" &&
        out.length &&
        out !== key &&
        !out.startsWith("MISSING KEY")
      ) {
        return fill(out, vars);
      }
    }
  } catch {
    /* fall through to catalogs */
  }
  const pack = messages[getAdminLocale()] || messages.en;
  const str = dig(pack, key) ?? dig(messages.en, key) ?? key;
  return fill(str, vars);
}
