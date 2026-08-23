# Material WARN + EN Description Hardening

> **For Claude:** Implement; skip commits unless asked.

**Goal:** Apparel missing/Chinese material → translate or WARN; mashed/Chinese descriptions → format + label EN + heavy-CJK → English summary AUTOFIX with WARN/log.

**Architecture:** Extend `desc_formatter.prepare_feed_description`; add M01/M02/M03 + D01/D02/D03 in `feed_quality.apply_row_autofixes` so store generate quality report surfaces issues before XML write.

---

### Task 1: Failing tests
### Task 2: desc_formatter prepare + feed_quality rules
### Task 3: pytest verify
