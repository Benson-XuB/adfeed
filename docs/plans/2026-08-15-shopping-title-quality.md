# Shopping Title Quality Implementation Plan

Field contract: `docs/plans/2026-08-14-feed-field-contract.md`  
North Star: `docs/plans/2026-08-12-mvp-north-star.md`  
Design: `docs/plans/2026-08-15-shopping-title-quality-design.md`

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align US shopping titles with the world apparel formula (skeleton contract + thin sanitize).

**Architecture:** `title_optimizer` prompt/premise authors Gender + ≤2 searchable attrs + product type; `title_guard.sanitize` strips banned junk; `polish_feed_title` still only appends this-row color+size.

**Tech Stack:** Python, pytest, existing title_optimizer / title_guard.

---

### Task 1: Failing tests for sanitize junk strip

**Files:**
- Modify: `phase0/tests/test_title_guard.py`
- Modify: `phase0/tests/test_title_scene_priority_prompt.py`

**Step 1:** Add tests that Closure / Fitted Fit / Polyester wall / `•` `|` are stripped; Denim / Floral kept; Fit remnant does not keep “Regular fit”.

**Step 2:** Extend prompt tests for world-formula strings in `_FEED_TITLE_PREMISE` / `_PROMPT_EN`.

**Step 3:** Run pytest — expect FAIL until Task 2–3.

### Task 2: Thin sanitize (no new selling points)

**Files:**
- Modify: `phase0/adfeed/title_guard.py`

Strip symbols and banned apparel-dump phrases; keep searchable materials (Denim, Leather, Silk, Cashmere, Merino, Cotton as whole words when not in a blend dump).

### Task 3: US prompt + premise

**Files:**
- Modify: `phase0/adfeed/title_optimizer.py`

Update `_FEED_TITLE_PREMISE` and EN Tier-1 to world formula; pattern priority; searchable material exception; ban Closure/Fit/fabric wall.

### Task 4: Verify

Run: `phase0/.venv/bin/python -m pytest tests/test_title_guard.py tests/test_title_scene_priority_prompt.py -q`  
Spot-check three skeletons through `polish_feed_title`.
