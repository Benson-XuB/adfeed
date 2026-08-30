# App Store review — testing instructions

Paste this block into Partner Dashboard → App listing → Testing instructions.

The app is **embedded (iframe App Home)**. After install, Admin opens the React Router app with a session token. **There is no extra AdFeed username or password.**

Support: support@deltfu.com  
Privacy: https://deltfu.com/api/privacy  

---

## What this app does

Generates **Google Shopping data feeds** for Shopify catalogs whose products were **imported from 1688**. Merchants confirm an **ad brand** (not the 1688 supplier name), pick a country, select products, generate, then copy a persistent feed URL into Google Merchant Center.

Access scopes: `read_products`, `write_products`, `read_legal_policies`.

- `read_products` — sync catalog for feed generation.
- `read_legal_policies` — read store policy URLs for compliance hints in App Home.
- `write_products` — **only** when you explicitly save a missing color/size on a product **not yet in the feed**. Updates that variant's Color/Size option in Shopify. Does not change title, price, images, or other catalog fields. Products already in the feed: fixes update the feed database only (no Shopify write).

Missing color/size are **optional suggestions** when Shopify has a Color/Size option to edit. Products without those options (e.g. demo snowboards) can generate without filling them. The app does **not** invent barcodes (GTIN) or product cost (COGS). It does **not** guarantee Google Merchant Center approval.

---

## Test store

Install on the review store (or any development store in this Partner org). Uninstall first if an older version is installed, then install the submitted version.

**Test account:** none beyond Shopify Admin. No demo username/password for AdFeed.

---

## Happy path (required)

1. Open **AdFeed AI** from Apps — you should see the **embedded React Router App Home** (nav: Home / Plans), not a JSON `Not Found` page.
2. Under **Ad brand**, enter `Review Brand` and click **Confirm brand**.
3. Leave **United States** selected under **Countries** (default).
4. In the product list, select at least one product with a photo.
5. Click **Generate feed** in the right sidebar. A confirm dialog lists selected products; keep them checked and confirm. Stay on the page until generation finishes.
6. In the sidebar, click **Copy** on the feed URL. Open the URL in a new tab — production feeds must be on `https://deltfu.com/...`, not a tunnel host.
7. Confirm the page did not show a 404 or 500.

## Billing (required)

8. Open **Plans** from the top nav.
9. Click **Switch to Starter** → approve the charge in Shopify.
10. Return to the app. Plan / quota should show Starter. Growth works the same way.

If the review store should not keep a paid charge, decline or cancel the subscription in Shopify after the test.

## Optional color / size fix

11. If a row shows a yellow **Suggested: Missing color/size** tip, you may click it to enter a real value (e.g. `Black` / `M`) and save. This is optional — you can generate without fixing. For products already in the feed, the fix updates the feed database only. For products not yet in the feed, saving may update that variant's Color/Size in Shopify when a Color/Size option exists.
12. Or open **Feed · N variants** on a generated row to edit SKU fields in the drawer (feed database only).
13. Do not paste a fake barcode / GTIN.

## Uninstall / privacy (optional but useful)

14. Uninstall the app. `app/uninstalled` should succeed (no merchant-facing error).
15. Shop data is erased on `shop/redact` (Shopify sends this about 48 hours after uninstall). Customers webhooks return 200; this app stores no customer PII.

---

## Do not test

- Do not expect title, price, or images to change in Shopify Admin. Color/size may update on a variant only when you save a fix on a product not yet in the feed and a Color/Size option exists.
- Do not require a GTIN. Leave barcode blank if the product has none.
- Do not treat feed generation as Google approval.
- Do not use a Cloudflare tunnel URL for production listing checks; production must be `deltfu.com`.
- Do not block on missing color/size for Title-only demo products — generate is allowed.
