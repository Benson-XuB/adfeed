# Store Website Compliance — Lite (MVP)

> Lightweight; does not block Feed generate.

**Goal:** One-click store diagnosis: Shopify Policies API + HTTPS + homepage footer policy links + common Contact URL probe + currency hint for selected markets.

**Out of scope:** Full crawl, checkout simulation, 22-item AdNabu-style scan.

**Footer checks (lite):** Parse homepage `<footer>` for links to refund/privacy/shipping/terms policies and Contact. `FOOT_*` pass = in footer; warn = elsewhere on page or missing. Reuses single homepage fetch.

**API:** `GET /api/app/store/compliance?countries=US`

**UI:** HomePage section — manual「一键诊断」button, checklist only.
