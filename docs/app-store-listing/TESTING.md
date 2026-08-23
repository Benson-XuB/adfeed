# App Store review — testing instructions

Paste this block into Partner Dashboard → App listing → Testing instructions.

The app is **embedded (iframe App Home)**. After install, Admin opens the React Router app with a session token. **There is no extra AdFeed username or password.**

Support: support@deltfu.com  
Privacy: https://deltfu.com/api/privacy  

---

## What this app does

Generates **Google Shopping** feeds from the Shopify product catalog. Merchants confirm an ad brand, pick a country, select products, generate, then copy a persistent feed URL into Google Merchant Center.

Access scopes: `read_products`, `write_products`, `read_legal_policies`.

- `read_products` — sync catalog for feed generation.
- `read_legal_policies` — read store policy URLs for compliance hints in App Home.
- `write_products` — **only** when you explicitly save a missing color/size on a product **not yet in the feed**. Updates that variant's Color/Size option in Shopify. Does not change title, price, images, or other catalog fields. Products already in the feed: fixes update the feed database only (no Shopify write).

It does **not** invent barcodes (GTIN) or product cost (COGS). It does **not** guarantee Google Merchant Center approval.

---

## Test store

Install on the review store (or any development store in this Partner org). Uninstall first if an older version is installed, then install the submitted version.

No demo-store login is required beyond Shopify Admin.

---

## Happy path (required)

1. Open **AdFeed AI** from Apps — you should see the **embedded React Router App Home** (nav: Home / Plans), not a JSON `Not Found` page.
2. Under **Ad brand**, enter `Review Brand` and click **Confirm brand**.
3. Leave **United States** selected under **Countries** (default).
4. In the product list, select at least one product with a photo.
5. Click **Generate feed** (top button) or **Generate feed** on a single product row. Stay on the page until it finishes.
6. In the sidebar, click **Copy** on the feed URL. Open the URL in a new tab — production feeds must be on `https://deltfu.com/...`, not a tunnel host.
7. Confirm the page did not show a 404 or 500.

## Billing (required)

8. Open **Plans** from the top nav.
9. Click **Switch to Starter** → approve the charge in Shopify.
10. Return to the app. Plan / quota should show Starter. Growth works the same way.

If the review store should not keep a paid charge, decline or cancel the subscription in Shopify after the test.

## Size / color fix (required)

11. After generate, if a product row shows **Missing size** or **Missing color** (red hint under the title), click **Fix & generate** on that row, enter a real size (e.g. `M`) or color, then save. For rows already in the feed, the fix updates the feed database only. For products not yet in the feed, saving also updates that variant's Color/Size in Shopify Admin.
12. Or open **Feed · N variants** on a generated row to edit SKU fields in the drawer (feed database only).
13. Do not paste a fake barcode / GTIN.

## Uninstall / privacy (optional but useful)

14. Uninstall the app. `app/uninstalled` should succeed (no merchant-facing error).
15. Shop data is erased on `shop/redact` (Shopify sends this about 48 hours after uninstall). Customers webhooks return 200; this app stores no customer PII.

---

## Do not test

- Do not expect title, price, or images to change in Shopify Admin. Color/size may update on a variant only when you save a fix on a product not yet in the feed.
- Do not require a GTIN. Leave barcode blank if the product has none.
- Do not treat feed generation as Google approval.
- Do not use a Cloudflare tunnel URL for production listing checks; production must be `deltfu.com`.
