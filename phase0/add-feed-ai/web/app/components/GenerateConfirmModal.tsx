import { useEffect, useMemo, useState } from "react";
import { t } from "../lib/i18n";
import type { WorkbenchProduct } from "../lib/adfeed-api";
import styles from "./GenerateConfirmModal.module.css";

export type GenerateConfirmItem = {
  id: string;
  title: string;
  image_url?: string;
  alreadyInFeed: boolean;
  feedItemCount: number;
};

type Props = {
  open: boolean;
  items: GenerateConfirmItem[];
  feedExists: boolean;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: (ids: string[]) => void;
};

export function buildGenerateConfirmItems(
  selectedIds: string[],
  rows: WorkbenchProduct[],
): GenerateConfirmItem[] {
  return selectedIds.map((id) => {
    const p = rows.find((r) => r.id === id);
    const st = p?.feed_status || "pending";
    const count = p?.feed_item_count || 0;
    const alreadyInFeed = st !== "pending" && count > 0;
    return {
      id,
      title: p?.title || id,
      image_url: p?.image_url || "",
      alreadyInFeed,
      feedItemCount: count,
    };
  });
}

export function GenerateConfirmModal({
  open,
  items,
  feedExists,
  busy,
  onCancel,
  onConfirm,
}: Props) {
  const [checked, setChecked] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!open) return;
    setChecked(new Set(items.map((i) => i.id)));
  }, [open, items]);

  const overwriteN = useMemo(
    () => items.filter((i) => i.alreadyInFeed && checked.has(i.id)).length,
    [items, checked],
  );
  const selectedN = checked.size;

  if (!open) return null;

  const toggle = (id: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className={styles.root} role="presentation">
      <button
        type="button"
        className={styles.backdrop}
        aria-label={t("genModal.close")}
        onClick={onCancel}
        disabled={busy}
      />
      <div
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="gen-confirm-title"
      >
        <h2 id="gen-confirm-title" className={styles.title}>
          {t("genModal.title")}
        </h2>
        <p className={styles.summary}>
          {feedExists
            ? overwriteN > 0
              ? t("genModal.summaryOverwrite", {
                  n: selectedN,
                  overwrite: overwriteN,
                })
              : t("genModal.summaryMerge", { n: selectedN })
            : t("genModal.summaryNew", { n: selectedN })}
        </p>
        <p className={styles.hint}>{t("genModal.uncheckHint")}</p>

        <ul className={styles.list}>
          {items.map((item) => {
            const on = checked.has(item.id);
            return (
              <li
                key={item.id}
                className={`${styles.row}${on ? "" : ` ${styles.rowOff}`}`}
              >
                <label className={styles.rowLabel}>
                  <input
                    type="checkbox"
                    checked={on}
                    disabled={busy}
                    onChange={() => toggle(item.id)}
                  />
                  {item.image_url ? (
                    <img
                      className={styles.thumb}
                      src={item.image_url}
                      alt=""
                    />
                  ) : (
                    <div className={styles.thumbEmpty}>—</div>
                  )}
                  <span className={styles.rowText}>
                    <span className={styles.rowTitle}>{item.title}</span>
                    {item.alreadyInFeed ? (
                      <span className={styles.badgeOverwrite}>
                        {t("genModal.willOverwrite", {
                          n: item.feedItemCount,
                        })}
                      </span>
                    ) : (
                      <span className={styles.badgeNew}>
                        {t("genModal.willAdd")}
                      </span>
                    )}
                  </span>
                </label>
              </li>
            );
          })}
        </ul>

        <div className={styles.actions}>
          <button
            type="button"
            className={styles.btnSecondary}
            disabled={busy}
            onClick={onCancel}
          >
            {t("genModal.cancel")}
          </button>
          <button
            type="button"
            className={styles.btnPrimary}
            disabled={busy || selectedN === 0}
            onClick={() => onConfirm([...checked])}
          >
            {busy
              ? t("cta.generating")
              : t("genModal.confirm", { n: selectedN })}
          </button>
        </div>
      </div>
    </div>
  );
}
