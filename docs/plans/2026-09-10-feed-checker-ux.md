# Feed Checker UX Implementation Plan

> **For Claude:** Implement task-by-task; landing-only deploy when done.

**Goal:** One-mode check console with URL row or dashed dropzone; fix dual-panel bug.

**Architecture:** Static HTML/CSS/JS on landing-page; no API changes.

**Tech Stack:** landing-page HTML, styles.css, feed-checker.js

---

### Task 1: HTML structure

**Files:** Modify `landing-page/tools/feed-checker.html`

- Wrap console in `.tools-console`
- Move privacy note under console
- Upload panel: dropzone + hidden file input + name + Check file
- Shorten lead slightly

### Task 2: CSS

**Files:** Modify `landing-page/styles.css`

- `[hidden] { display: none !important }` for tools panels
- `.tools-console`, segmented tabs, dropzone states, mobile stack

### Task 3: JS

**Files:** Modify `landing-page/tools/feed-checker.js`

- Tab switch + aria
- Dropzone click/drag/drop + XML validate
- Enter on URL triggers check
- Update file name label

### Task 4: Deploy

Landing-only deploy; curl `/tools/feed-checker` → 200
