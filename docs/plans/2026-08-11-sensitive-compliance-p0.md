# S6 Sensitive Compliance P0 — Implementation Plan

> **For Claude:** Implement task-by-task; skip commits unless user asks.

**Goal:** Tier sensitive handling (SOFT / ADULT / BLOCK), stop over-tagging plain underwear as adult, and add landing-page sync suggestions on soften/adult events.

**Architecture:** Keep lexicon engine in `sensitive_compliance.py`. Map `severity` to QualityEvent levels. Remove broad `underwear`→adult rule; adult only on strong signals. Append Shopify sync suggestion text when text changes or adult is forced.

**Tech stack:** Python, existing `QualityEvent` / tests under `phase0/tests/`.

---

### Task 1: Failing tests for P0 behavior
### Task 2: Implement lexicon tiers + underwear tighten + LP hint
### Task 3: Run `pytest tests/test_sensitive_compliance.py`
