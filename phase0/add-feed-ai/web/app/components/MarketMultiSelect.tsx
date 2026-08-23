import { useEffect, useMemo, useRef, useState } from "react";
import { t } from "../lib/i18n";
import type { TargetMarket } from "../lib/markets";
import styles from "./FeedWorkbench.module.css";

type Props = {
  markets: readonly TargetMarket[] | null;
  selected: Set<string>;
  disabled?: boolean;
  checkingCode?: string;
  onToggle: (code: string) => void | Promise<void>;
};

export function MarketMultiSelect({
  markets,
  selected,
  disabled,
  checkingCode,
  onToggle,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const summary = useMemo(() => {
    if (markets === null) return t("setup.loadingMarkets");
    if (checkingCode) return t("setup.checkingMarket");
    const codes = [...selected];
    if (!codes.length) return t("setup.pickMarkets");
    if (codes.length === 1) {
      const code = codes[0];
      const meta = markets.find((m) => m.code === code);
      return meta
        ? `${t(`setup.country.${code}`)} · ${meta.currency}`
        : t(`setup.country.${code}`);
    }
    return t("setup.marketsSelected", { n: codes.length });
  }, [selected, checkingCode, markets]);

  const filtered = useMemo(() => {
    const pool = markets ?? [];
    const q = query.trim().toLowerCase();
    if (!q) return pool;
    return pool.filter((c) => {
      const label = t(`setup.country.${c.code}`).toLowerCase();
      return (
        label.includes(q) ||
        c.code.toLowerCase().includes(q) ||
        c.currency.toLowerCase().includes(q)
      );
    });
  }, [query, markets]);

  return (
    <div className={styles.marketSelect} ref={rootRef}>
      <button
        type="button"
        className={styles.marketSelectTrigger}
        disabled={disabled || !!checkingCode || markets === null}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span className={styles.marketSelectSummary}>{summary}</span>
        <span className={styles.marketSelectChevron} aria-hidden>
          ▾
        </span>
      </button>
      {open ? (
        <div className={styles.marketSelectPanel} role="listbox" aria-multiselectable>
          <input
            className={styles.marketSelectSearch}
            type="search"
            value={query}
            placeholder={t("setup.searchMarkets")}
            onChange={(e) => setQuery(e.target.value)}
          />
          <ul className={styles.marketSelectList}>
            {filtered.map((c) => {
              const checked = selected.has(c.code);
              const busy = checkingCode === c.code;
              return (
                <li key={c.code}>
                  <label className={styles.marketSelectOption}>
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={disabled || busy}
                      onChange={() => void onToggle(c.code)}
                    />
                    <span className={styles.marketSelectLabel}>
                      {busy ? "…" : t(`setup.country.${c.code}`)}
                    </span>
                    <span className={styles.marketSelectCcy}>{c.currency}</span>
                  </label>
                </li>
              );
            })}
            {!filtered.length ? (
              <li className={styles.marketSelectEmpty}>
                {markets?.length === 0
                  ? t("setup.noCompatibleMarkets")
                  : t("setup.noMarketMatch")}
              </li>
            ) : null}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
