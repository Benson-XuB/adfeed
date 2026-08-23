/**
 * UI copy is English-only for App Store / cross-border merchants.
 * zh-CN strings remain in i18n-messages.js for a future locale toggle.
 */
import { messages } from "./i18n-messages.js";

export type Locale = "en" | "zh-CN";

export function getAdminLocale(): Locale {
  return "en";
}

function dig(obj: unknown, key: string): unknown {
  return String(key)
    .split(".")
    .reduce((acc: unknown, part) => {
      if (acc == null || typeof acc !== "object") return undefined;
      return (acc as Record<string, unknown>)[part];
    }, obj);
}

function fill(str: string, vars: Record<string, string | number | undefined>) {
  return String(str).replace(/\{\{(\w+)\}\}/g, (_, k: string) =>
    vars[k] != null ? String(vars[k]) : `{{${k}}}`,
  );
}

export function t(
  key: string,
  vars: Record<string, string | number | undefined> = {},
): string {
  const pack = (messages as Record<string, unknown>).en;
  const str = dig(pack, key) ?? key;
  return fill(typeof str === "string" ? str : String(key), vars);
}
