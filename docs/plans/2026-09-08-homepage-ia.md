# Homepage IA 收口 Implementation Plan

> **For Claude:** Implement task-by-task on landing-only surface.

**Goal:** Restructure `landing-page/index.html` into Diagnose → Fix → Generate → Publish without adding pages or App changes.

**Architecture:** Single-page section reorder + copy/CSS. Demo merges into How it works. Nav/footer align to design.

**Tech Stack:** Static HTML/CSS on `landing-page/`; deploy via `deploy-landing-only.sh`.

---

### Task 1: Nav + Hero + Compare position

**Files:** `landing-page/index.html`, `landing-page/styles.css`

- Nav: Free tools, How it works, Pricing, Guides, Get early access
- Hero slim copy; secondary Check my feed; Before/After after waitlist

### Task 2: Diagnose + How + Demo merge

- Add diagnose two-card section
- Rewrite three steps (product brand language)
- Move video into How; delete `#demo` section
- Retarget waitlist success demo link → `#how`

### Task 3: Pricing + FAQ + footer

- Products × markets on cards; FAQ for unit math
- Footer: Setup under secondary links only

### Task 4: Verify + landing-only deploy

- Curl homepage anchors/copy; confirm tools still 200; no adfeed-web restart
