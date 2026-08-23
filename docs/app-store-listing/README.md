# App Store listing pack — ready to paste

**Self-test:** `python3 docs/app-store-listing/self_test.py` → must print `PASS`.

This folder is everything for Partner Dashboard listing media + copy. It does **not** change Feed field owners.

## Paste / upload order

1. Open Partner Dashboard → your app → Distribution → Shopify App Store listing.
2. Paste English fields from `LISTING.md` (subtitle, introduction, details, features).
3. Paste **Pricing details** only into the pricing field (prices live nowhere else).
4. Paste Chinese fields from the same file if the form has a zh-CN locale.
5. Privacy URL: `https://deltfu.com/api/privacy`
6. Support URL: `https://deltfu.com/api/support`
7. Upload `icon-1200.png`
8. Upload screenshots `01`–`05` (not `06`)
9. Upload `screencast/adfeed-ai-screencast.mp4` to YouTube or Loom (unlisted), paste the URL
10. Paste all of `TESTING.md` into Testing instructions
11. Opt out of Protected Customer Data; tags = marketing / product feeds (not sales channel)

## Rebuild assets

```bash
docs/app-store-listing/render_assets.sh
python3 docs/app-store-listing/self_test.py
```

## Honest notes for review day

- Screenshots and the screencast are **English App Home replicas** matched to shipped locale strings (confirm brand → generate → fix size → copy URL → ad image → change plan). Record a live Admin capture later if you want pixel-perfect store UI; do not delay the listing pack for that.
- Partner Dashboard **Submit for review** still needs your Partner login — this pack is the paste payload.
- Production API on `deltfu.com` must be running the latest FastAPI (privacy/support under `/api/*`, GDPR purge, GraphQL Admin, billing `test=false`) before you click submit.
