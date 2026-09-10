# Feed Checker tool UX redesign

Date: 2026-09-10  
Approved: Approach A + dashed drag-drop upload

## Problem

- Segmented tabs coexist with both URL and file panels → double CTAs, unclear action.
- Native file input looks unfinished.
- Privacy note interrupts title → action flow.
- `.tools-panel { display: flex }` can defeat `[hidden]`.

## Solution

1. One check console: tab shows only one mode.
2. URL: single row input + one primary `Check feed`.
3. Upload: dashed dropzone (click/drag) + file name + one `Check file`.
4. Privacy line under the console.
5. Fix `[hidden] { display: none !important }`.

## Out of scope

Report API/buckets, homepage IA, other tools pages.
