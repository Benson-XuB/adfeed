# Landing published CTA — Implementation Plan

> **For Claude:** implement task-by-task; landing-only deploy.

**Goal:** Replace waitlist / early-access CTAs with Install on Shopify across the marketing site.

**Architecture:** Static HTML/JS on `landing-page/`. Single App Store URL with per-page `utm_source=deltfu&utm_medium=<page>`. `#waitlist` hashes redirect or rewrite to `#install` / App Store.

**Tech Stack:** HTML, existing CSS (reuse `.btn`, `.cta-row`, `.waitlist-note`), `deploy-landing-only.sh`

---

### Task 1: Homepage hero + CTAs

**Files:** `landing-page/index.html`

- Nav / footer / section buttons → Install
- Hero: drop email form; Install + free tools
- Anchor `#install`; tiny script maps `#waitlist` → `#install`

### Task 2: Tools pages

**Files:** `landing-page/tools/*.html`, `google-issues.js`, `feed-checker` CTA copy

- Nav + bottom CTA blocks → Install
- Remove waitlist forms; drop waitlist.js where unused

### Task 3: Guides + setup + waitlist.html

**Files:** `landing-page/guides/*.html`, `setup.html`, `waitlist.html`

- Early access → Install
- Strip “review in progress / join waitlist” lines
- `waitlist.html` → redirect to App Store or `/#install`

### Task 4: Deploy

`SERVER=… deploy-landing-only.sh`; spot-check homepage + one tool.
