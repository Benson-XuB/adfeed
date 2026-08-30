/** UI copy catalogs — locale follows Shopify admin language (zh* → zh-CN, else en). */
export const messages = {
  en: {
  "name": "AdFeed AI",
  "welcome": "AdFeed AI — Google Shopping Feed",
  "gmc": {
    "issuesTitle": "Review issues",
    "issuesHint": "After your feed is in Merchant Center, sync disapproval reasons here. Manual sync only.",
    "oauthNotConfigured": "Google OAuth is not configured on this server yet (set GOOGLE_OAUTH_*).",
    "connectLater": "Connect Google after server OAuth is configured.",
    "connect": "Connect Google",
    "disconnect": "Disconnect",
    "refreshMerchants": "Refresh accounts",
    "merchant": "Merchant account",
    "selectMerchant": "Select…",
    "sync": "Sync issues",
    "empty": "No cached issues yet. Sync after connecting Google.",
    "unmatched": "Unmatched offer",
    "matchStats": "Matched {{matched}} · unmatched {{unmatched}}"
  },
  "ads": {
    "metricsTitle": "Ad performance",
    "metricsHint": "Product-level Shopping metrics when available. Read-only; manual sync.",
    "needGoogleFirst": "Connect Google in Review issues first.",
    "connectAds": "Allow Ads read access",
    "customerId": "Ads customer ID",
    "sync": "Sync metrics",
    "devTokenMissing": "Server missing GOOGLE_ADS_DEVELOPER_TOKEN — metrics sync disabled.",
    "degraded": "No product-level rows — showing campaign/account totals.",
    "productLevel": "{{n}} product-level rows",
    "rowStats": "{{imps}} imps · {{clicks}} clicks · {{cost}}",
    "empty": "No cached metrics yet."
  },
  "meta": {
    "catalogTitle": "Meta catalog",
    "catalogHint": "Connect Meta, pick a catalog, and schedule Meta to fetch your AdFeed XML URL.",
    "oauthNotConfigured": "Meta OAuth is not configured on this server yet (set META_*).",
    "connect": "Connect Meta",
    "disconnect": "Disconnect",
    "catalog": "Catalog",
    "selectCatalog": "Select…",
    "refreshCatalogs": "Refresh catalogs",
    "attachFeed": "Attach feed URL",
    "attachOk": "Scheduled feed {{feedId}}. Meta will fetch your Meta feed URL.",
    "syncIssues": "Sync review issues",
    "issuesEmpty": "No cached Meta review issues. Sync after connecting.",
    "unmatched": "Unmatched offer",
    "matchStats": "Matched {{matched}} · unmatched {{unmatched}}"
  },
  "tiktok": {
    "shopTitle": "TikTok Shop",
    "shopHint": "Connect TikTok Shop, pick a shop, and register your AdFeed CSV URL (no invented weights).",
    "oauthNotConfigured": "TikTok OAuth is not configured on this server yet (set TIKTOK_*).",
    "connect": "Connect TikTok",
    "disconnect": "Disconnect",
    "shop": "Shop",
    "selectShop": "Select…",
    "refreshShops": "Refresh shops",
    "attachFeed": "Register feed URL",
    "attachOk": "Registered CSV URL: {{url}}",
    "syncIssues": "Sync listing issues",
    "issuesEmpty": "No cached TikTok listing issues. Sync after connecting.",
    "unmatched": "Unmatched offer",
    "matchStats": "Matched {{matched}} · unmatched {{unmatched}}"
  },
  "cta": {
    "generate": "Generate feed",
    "create": "Generate feed",
    "updateWide": "Generate feed",
    "update": "Generate feed",
    "generating": "Working…",
    "needBrand": "Confirm brand below first",
    "selectVisible": "Select all in list",
    "meta": "{{n}} selected · {{platform}} · {{market}}",
    "sub": "Write {{n}} products into the feed"
  },
  "genModal": {
    "title": "Confirm feed generate",
    "summaryNew": "Generate feed for {{n}} selected product(s).",
    "summaryMerge": "Add {{n}} product(s) into the current feed. Other items stay.",
    "summaryOverwrite": "{{n}} selected · {{overwrite}} already in feed will be overwritten.",
    "uncheckHint": "Uncheck any product to skip it this time.",
    "willOverwrite": "Already in feed · will overwrite ({{n}} variants)",
    "willAdd": "New · will add to feed",
    "cancel": "Cancel",
    "confirm": "Generate {{n}}",
    "close": "Close"
  },
  "hub": {
    "title": "Feed Generator Hub",
    "panel": "HUB PANEL",
    "subtitle": "Pick a product scope (with photos), choose markets, then create a Google-ready feed.",
    "scopeHeading": "1. Product scope",
    "scopeHelp": "Tap All, Uncategorized, or a product type to set the scope.",
    "productsInScope": "In this scope: {{selected}} selected / {{total}}",
    "emptyScope": "No products in this scope.",
    "productListScroll": "{{n}} products — scroll the list to see all.",
    "productListPrev": "Previous 5",
    "productListNext": "Next 5",
    "productListPage": "{{from}}–{{to}} of {{n}}",
    "marketHeading": "2. Channels & markets",
    "statsHeading": "At a glance",
    "statsHint": "From your last generate — not Google approval status.",
    "activeFeeds": "Active feeds",
    "checklistHeading": "Store to-dos",
    "checklistHelp": "Only open items. Fix in Shopify, then tap Check again.",
    "feedsHeading": "Copy for Merchant Center",
    "createHeading": "3. Create feed",
    "createHint": "Full-width button.",
    "scopeThenMarket": "Next: pick countries below, then tap Generate feed.",
    "needProducts": "Select products below to include in the feed.",
    "productListHeading": "Products in this scope (optional fine-tune)",
    "setupCard": "Generate ad feed",
    "productsCard": "Products in this feed"
  },
  "overview": {
    "heading": "Feed status",
    "needsAttention": "Needs attention · {{n}}",
    "ready": "Ready to advertise · {{n}}",
    "selected": "Selected in scope · {{n}}",
    "panelNeeds": "Needs attention",
    "panelReady": "Ready to advertise",
    "panelSelected": "Selected",
    "kpiNeeds": "To fix",
    "kpiNeedsHint": "Color, size, image, or sensitive wording",
    "kpiReady": "In this feed",
    "kpiReadyHint": "Rows written for one market — not Google-approved",
    "kpiReadyUnknown": "—",
    "kpiReadyUnknownHint": "Available after generate",
    "kpiFeeds": "Ad links",
    "kpiFeedsHint": "Generated URLs to copy into the ads backend",
    "kpiTapHint": "",
    "kpiNeedsAction": "Fix these {{n}}",
    "kpiNeedsActionEmpty": "Nothing to fix",
    "kpiNeedsCollapse": "Hide",
    "kpiNeedsStoreOnly": "No product fixes. Brand, currency, and site items are in Store to-dos below.",
    "kpiReadyAction": "Details",
    "kpiFeedsAction": "Copy links",
    "kpiFeedsCollapse": "Hide",
    "noneYet": "No ad links yet — select products, then generate.",
    "emptyNeeds": "Nothing to fix right now.",
    "showFeeds": "Feed links are below.",
    "storeBrandGate": "Confirm your ad brand before generating.",
    "storeCurrencyGate": "Currency blocks {{count}} market(s) — fix in Shopify or change markets.",
    "adjustScope": "Adjust product scope & update",
    "hideScope": "Hide product scope",
    "storeTodos": "Store to-dos",
    "storeTodosHelp": "Only open items. Fix in Shopify or confirm brand below."
  },
  "scope": {
    "heading": "1. Which products",
    "help": "Pick a type, then check the photos — you should recognize each item.",
    "allActive": "All active ({{n}})",
    "uncategorized": "Uncategorized ({{n}})",
    "typeChip": "{{type}} ({{n}})",
    "myStoreType": "My store",
    "inScope": "{{selected}} selected · {{total}} in this scope",
    "selectScope": "Select all in this scope",
    "needsChip": "To fix ({{n}})"
  },
  "intro": {
    "heading": "Before you advertise, run a feed check",
    "body": "We do not promise Google approval. We first turn titles, color/size, the no-barcode path, and main images into a shopping-ready feed so you can see what changed, then hand the link to Merchant Center. We never invent barcodes or COGS — add real ones below if you have them.",
    "note": "After submit, Google often shows Limited / Pending initial review. That is the first-review queue (a few business days), not an App failure."
  },
  "setup": {
    "heading": "2. Where to advertise",
    "platforms": "Ad platforms",
    "markets": "Countries",
    "marketsWithCcy": "Countries",
    "storeCcy": "Store checkout is {{ccy}}. Feed uses the price buyers see on that country’s page — we never convert by exchange rate.",
    "marketsHelp": "Each chip is the currency that market’s landing page must show. Pick DE only after Shopify Markets shows EUR there.",
    "marketLocked": "Enable {{country}} in Shopify Markets and show {{expected}} first.",
    "needOneMarket": "Keep at least one country selected.",
    "checkingMarket": "Checking that market’s storefront currency…",
    "country": {
      "US": "United States",
      "CA": "Canada",
      "GB": "United Kingdom",
      "DE": "Germany",
      "FR": "France",
      "ES": "Spain",
      "IT": "Italy",
      "NL": "Netherlands",
      "BE": "Belgium",
      "AT": "Austria",
      "IE": "Ireland",
      "PT": "Portugal",
      "FI": "Finland",
      "SE": "Sweden",
      "NO": "Norway",
      "DK": "Denmark",
      "CH": "Switzerland",
      "PL": "Poland",
      "AU": "Australia",
      "NZ": "New Zealand",
      "JP": "Japan",
      "KR": "South Korea",
      "SG": "Singapore",
      "HK": "Hong Kong",
      "TW": "Taiwan",
      "QA": "Qatar",
      "AE": "UAE"
    },
    "ccy": {
      "USD": "US dollars",
      "EUR": "euros",
      "GBP": "British pounds",
      "CAD": "Canadian dollars",
      "AUD": "Australian dollars",
      "NZD": "New Zealand dollars",
      "JPY": "Japanese yen",
      "KRW": "Korean won",
      "SGD": "Singapore dollars",
      "HKD": "Hong Kong dollars",
      "TWD": "New Taiwan dollars",
      "QAR": "Qatari riyal",
      "AED": "UAE dirham",
      "SEK": "Swedish krona",
      "NOK": "Norwegian krone",
      "DKK": "Danish krone",
      "CHF": "Swiss franc",
      "PLN": "Polish zloty"
    },
    "needOneMarket": "Keep at least one country selected.",
    "checkingMarket": "Checking that market’s storefront currency…",
    "pickPlatforms": "Select channels",
    "pickMarkets": "Select markets",
    "marketsSelected": "{{n}} countries selected",
    "searchMarkets": "Search countries…",
    "noMarketMatch": "No matching country",
    "loadingMarkets": "Loading compatible countries…",
    "noCompatibleMarkets": "No feed-ready countries yet. Enable a market in Shopify and show the matching currency on that country’s storefront page."
  },
  "storeWarnings": {
    "heading": "Store setup checks",
    "help": "Fix these so ads and the feed are less likely to get stuck. They do not replace selecting products above."
  },
  "pipeline": {
    "heading": "Generating",
    "headingDone": "Generated",
    "headingCollapsed": "Generated",
    "doneHint": "Fix color or size on the products listed under To fix.",
    "stay": "Stay on this page. When finished we mark color/size changes so you can fix them in one click.",
    "hideSteps": "Hide steps",
    "showSteps": "Show five steps",
    "badgeDone": "Done",
    "badgeActive": "Running",
    "badgeWait": "Waiting",
    "steps": {
      "title": {
        "label": "Title",
        "copy": "Turning supplier-style titles into Google Shopping structure…"
      },
      "category": {
        "label": "Category",
        "copy": "Matching products to standard categories…"
      },
      "variant": {
        "label": "Color / size",
        "copy": "Checking each color and size; gaps get a smart fill you can edit…"
      },
      "id": {
        "label": "Barcode / no-ID path",
        "copy": "No real barcode → open the no-ID path (no fake codes). Add UPC/EAN on Shopify variants if you have them…"
      },
      "image": {
        "label": "Ad image",
        "copy": "Checking if the main image looks like wholesale stock so you can swap a clean store photo…"
      }
    }
  },
  "quota": {
    "heading": "Quota",
    "remaining": "{{used}} / {{total}} ({{left}} left)",
    "estimate": "Estimated use: {{skus}} SKUs × {{platforms}} platforms × {{markets}} markets =",
    "insufficient": " — not enough quota, please upgrade"
  },
  "billing": {
    "current": "Plan: {{plan}} · {{left}} / {{total}} generate units left",
    "headerQuota": "{{plan}} · {{left}} / {{total}}",
    "plan_free": "Free",
    "plan_starter": "Starter ($14.99/mo, 50)",
    "plan_growth": "Growth ($39/mo, 200)",
    "chooseStarter": "Switch to Starter",
    "chooseGrowth": "Switch to Growth",
    "approveInShopify": "Approve charge in Shopify",
    "approveHint": "Tap Approve charge in Shopify, then come back here.",
    "subscribeFailed": "Could not start billing: {{detail}}",
    "plans": {
      "open": "Upgrade plan",
      "back": "Back",
      "pageTitle": "Choose a plan",
      "pageIntro": "Compare Free, Starter, and Growth. Pick a paid plan to continue in Shopify checkout.",
      "howQuota": "Quota = parent products × ad platforms × markets (not variants). One product with 5 colors × 5 sizes still counts as 1 unit for Google + US.",
      "currentBadge": "Current",
      "included": "Included",
      "choose": "Choose {{plan}}",
      "starting": "Starting…",
      "free": {
        "name": "Free",
        "price": "$0 / month",
        "quota": "3 generate units / month",
        "blurb": "Try the flow on a small catalog."
      },
      "starter": {
        "name": "Starter",
        "price": "$14.99 / month",
        "quota": "50 generate units / month",
        "blurb": "For shops running Google Shopping regularly."
      },
      "growth": {
        "name": "Growth",
        "price": "$39 / month",
        "quota": "200 generate units / month",
        "blurb": "For multi-platform / multi-market catalogs."
      }
    }
  },
  "brand": {
    "heading": "Ad brand (written to feed)",
    "help": "This is the store-wide brand written to every feed item (g:brand). Shopify product Vendor is often a supplier name (e.g. eprolo) — we do not copy it automatically. Confirm once; only tap again if you change it.",
    "warn": "Ad brand not confirmed. Enter it and tap Confirm brand, or feed generation stays blocked (avoids Missing brand disapprovals).",
    "confirmed": "Ad brand: {{brand}}",
    "label": "Ad brand",
    "placeholder": "e.g. your store name or own brand",
    "saving": "Saving…",
    "confirm": "Confirm brand",
    "update": "Update brand",
    "change": "Change",
    "cancelEdit": "Cancel"
  },
  "merchantData": {
    "heading": "Barcode & cost (optional)",
    "help": "Does not block feed generation. We never invent barcodes or COGS; real data improves matching and profit reports.",
    "gtinTitle": "Barcode / GTIN",
    "gtinShort": "Optional — add real UPC/EAN on Shopify variants; never invent digits.",
    "gtinBody": "No barcode is fine: we use the no-ID path and keep the ad brand above. If packaging has a real UPC/EAN, add it under Shopify → product → variant Barcode; the next generate writes g:gtin. Leave blank if you have no real code — do not invent digits.",
    "cogsTitle": "Cost (COGS)",
    "cogsShort": "Optional — leave blank if unknown; do not invent costs.",
    "cogsBody": "Not required for free listings. If you know true cost, set Shopify variant Cost for profit reports later; otherwise leave blank — do not invent estimates."
  },
  "compliance": {
    "heading": "Is the site ready for ads?",
    "help": "Checks policy pages, footer links, HTTPS, and selected-market currency. Google looks at these too; this does not block feed generation.",
    "run": "Run check",
    "running": "Checking…",
    "summary": "Pass {{pass}} · Suggestions {{warn}} · Missing {{fail}}",
    "colId": "Item",
    "colStatus": "Status",
    "colNote": "Notes",
    "lightGreen": "Pass",
    "lightYellow": "Suggestions",
    "lightRed": "Gaps",
    "statusWarn": "Suggestion",
    "statusFail": "Missing",
    "allPass": "No open store issues for this check.",
    "needRun": "Tap Run check to scan policies, footer links, and HTTPS.",
    "currencyOk": "Selected market currency matches the store (or is usable)",
    "openHeading": "To fix ({{n}})",
    "doneHeading": "Done ({{n}})",
    "doneBadge": "Done",
    "fixInShopify": "Open in Shopify",
    "fixMenus": "Open footer menus",
    "fixLegal": "Open legal / policies",
    "fixMarkets": "Open Markets",
    "fixPages": "Open pages"
  },
  "currency": {
    "mismatchBanner": "Selected {{markets}}; store currency is {{shop}}. Align Shopify presentment currency before generating (App only detects — no auto FX).",
    "blockedHeading": "Currency mismatch (blocked)",
    "shopNeeds": "Store {{shop}} → needs {{expected}}",
    "fixHint": "In Shopify, set presentment currency to match the selected market, then generate again."
  },
  "quality": {
    "heading": "This round (details)",
    "lightGreen": "Ready to submit to Google",
    "lightYellow": "We filled gaps — spot-check first",
    "lightRed": "High risk — review before ads",
    "bodyGreen": "Required fields look complete. Next: copy the feed link below into Google Merchant Center. Approval is still Google’s call; new stores often wait a few days for initial review.",
    "bodyGreenShort": "Looks submit-ready. Copy the link above into Merchant Center. Google’s review can take a few days.",
    "bodyYellow": "Auto-fixed {{auto}} items (e.g. color/size fallbacks, no-barcode path). {{warn}} items need a spot-check. Missing barcode or COGS is not a disapproval reason; add real values in Shopify if you have them. This is not “approved” — it means “ok to submit, look first.”",
    "bodyYellowShort": "Auto-fixed {{auto}} items. {{review}} need a real color/size or image — select them below and fix in one go (no quota).",
    "bodyRed": "{{fatals}} high-risk items are still in the feed. Fix the red list below before treating this as ad-ready.",
    "counts": "Auto-fixed {{auto}} · Spot-check {{warn}} · High risk {{fatals}}",
    "missingVariantId": "{{count}} variants lack a Shopify Variant ID, so links cannot target color/size. Re-sync products, then regenerate; do not advertise those SKUs until fixed (no internal fake IDs).",
    "logTitle": "Optimization log",
    "detailsHeading": "Technical details",
    "expandDetails": "Show details",
    "collapse": "Collapse",
    "expand": "Expand first {{n}}",
    "logMore": "{{n}} more auto-fixes not shown",
    "titleCompare": "How titles got clearer",
    "titleCompareHelp": "Store title → shopping-style ad title.",
    "titleBefore": "Before: {{title}}",
    "titleAfter": "Ad title: {{title}}",
    "confirmHeading": "Needs attention — fix what you want, then update",
    "confirmHelp": "These are suggestions. Fix color/size/image here or edit in Shopify. You can update the feed without clearing every item.",
    "bulkHelp": "Use Fix all variants for many rows. Tap Add size on one row to edit only that row.",
    "bulkHint": "Tip: tap “Select all in bucket”, enter a real color or size, then Apply.",
    "applying": "Applying…",
    "sensitiveTitle": "Sensitive copy · {{count}}",
    "sensitiveHelp": "Phrases softened or marked adult — edit in Shopify if needed.",
    "colSku": "SKU",
    "colProduct": "Product",
    "colRule": "Rule",
    "colNote": "Notes",
    "colField": "Field",
    "colResult": "Result",
    "imageTitle": "Main image · {{count}}",
    "imageHelp": "Pick a cleaner photo for ads (does not change Shopify).",
    "changeImage": "Change image",
    "mcTitle": "Missing color · Multicolor · {{count}}",
    "osTitle": "Missing size · One Size · {{count}}",
    "selectBucket": "Select all",
    "bulkTitle": "Fix {{count}} selected — one apply",
    "color": "Color",
    "colorPh": "e.g. Black",
    "applyColor": "Apply color",
    "oneSizeBtn": "Keep One Size",
    "size": "Size",
    "sizePh": "e.g. M / L / XL",
    "applySize": "Apply size",
    "clearSelection": "Clear",
    "checklist": {
      "shipping": "Before uploading to Google, confirm shipping is configured in Merchant Center for the target country",
      "claim": "Confirm the website is claimed and product pages are publicly reachable",
      "fatal": "If red FATAL items remain, uploading is at your own disapproval risk"
    }
  },

  "workbench": {
    "heading": "Smart Feed Optimization Workbench",
    "search": "Search products",
    "channels": "Channels",
    "itemsInFeed": "{{n}} feed rows",
    "tagPending": "Generate feed",
    "actionGenerateFeed": "Generate feed",
    "tagInFeed": "Feed · {{n}} variants",
    "tagFailed": "Generation failed",
    "defectsLine": "Suggested: {{list}}",
    "fixThenGenerate": "Fix & generate",
    "fixOptional": "optional fix",
    "edit": "Edit feed",
    "statusReady": "Ready",
    "statusMissing": "Missing Info",
    "statusWarn": "Needs review",
    "statusPending": "Not generated",
    "statusPendingHint": "Not in the current feed yet — click Generate into feed on this row (keeps other items).",
    "editAfterGenerate": "Generate first",
    "generateOne": "Generate into feed",
    "tableHelp": "Ready / Missing Info = already in feed (then Edit feed). Not generated = click Generate into feed on that row, or multi-select → Generate/Update above.",
    "needsChip": "Needs attention · {{n}}",
    "needsBanner": "{{n}} products are missing color and/or size in Shopify variants — fix in Shopify or edit after generate. Use the chip to filter.",
    "hintMissingColor": "Missing color",
    "hintMissingSize": "Missing size",
    "hintMissingImage": "Main image needs a better pick",
    "fixColorTitle": "Add color: {{title}}",
    "fixSizeTitle": "Add size: {{title}}",
    "fixColorHelp": "Enter a real color (e.g. Black). It will apply to this product’s variants.",
    "fixSizeHelp": "Enter a real size (e.g. M / One Size). It will apply to this product’s variants.",
    "fixColorPrompt": "This product is missing color — fill once and apply to all SKUs, then Save.",
    "fixSizePrompt": "This product is missing size — fill once and apply to all SKUs, then Save.",
    "applyToAllSkus": "Apply to all SKUs",
    "bulkColorApplied": "Filled color {{value}} on all SKUs — tap Save to write the feed.",
    "bulkSizeApplied": "Filled size {{value}} on all SKUs — tap Save to write the feed.",
    "fixNeedValue": "Enter a value first",
    "fixNoSkus": "No variants found for this product — sync or generate first.",
    "fixSavedInFeed": "Saved and updated the current feed.",
    "fixSavedShopify": "Saved to Shopify — you can now generate into feed on this row.",
    "fixSavedNeedGenerate": "Saved on variants — click Generate into feed on this row to write XML.",
    "fixSave": "Save",
    "emptyProducts": "No products loaded",
    "compliance": "Store checklist",
    "complianceSummary": "{{warn}} suggestions",
    "complianceSummaryClear": "No suggestions",
    "complianceSummaryUnknown": "{{unknown}} could not be checked",
    "complianceEmpty": "Checking store policies and contact…",
    "liveFeed": "Live XML feed",
    "editingFeed": "Editing feed",
    "editingFeedHint": "Switch market to edit that country's XML. Generate targets above are separate.",
    "needGenerate": "Generate a feed first to preview and edit items",
    "drawerTitle": "Edit feed attributes: {{title}}",
    "drawerHint": "Edits Google Shopping feed fields only (title / color / size / image). Does not change your Shopify product page.",
    "noFeedItems": "This product is not in the current feed. Click Generate into feed on the row, or select it and Generate/Update above.",
    "close": "Close",
    "cancel": "Cancel",
    "saveApply": "Save & apply to current feed",
    "deleteFeedRow": "Remove from feed"
  },
  "feeds": {
    "heading": "Multilingual Google Shopping feed links",
    "help": "Copy into Google Merchant Center. Limited after submit is usually first-review queue.",
    "items": "{{count}} products",
    "listedCount": "Feed items",
    "synced": "Generated",
    "preparing": "Not generated yet",
    "urlLabel": "Feed URL",
    "copy": "Copy link",
    "copyShort": "Copy",
    "copied": "URL copied",

    "viewItems": "View / edit items",
    "hidePreview": "Hide items",
    "downloadCsv": "Download CSV",
    "openXml": "Open XML",
    "openRawXml": "Raw XML",
    "editFeed": "View / edit feed",
    "editAllFeed": "Edit all feed items",
    "backToWorkbench": "Back to workbench",
    "pageHeading": "Feed editor",
    "pageTitle": "{{platform}} · {{market}}",
    "pageMeta": "{{count}} items · updated {{updated}}",
    "applyEditsWithCount": "Apply ({{n}} changed)",
    "copyFailed": "Could not copy URL",
    "search": "Search SKU or title",
    "searchBtn": "Search",
    "previewCount": "Showing {{shown}} of {{total}}",
    "loading": "Loading…",
    "colTitle": "Title",
    "colColor": "Color",
    "colSize": "Size",
    "colAdTitle": "Feed title",
    "colAdColor": "Feed color",
    "colAdSize": "Feed size",
    "pickImage": "Pick feed image",
    "prev": "Previous",
    "next": "Next",
    "applyEdits": "Apply to current feed",
    "applying": "Applying…",
    "applyOk": "Edits applied and feed updated",
    "saveRow": "Save",
    "savingRow": "Saving…",
    "deleteRow": "Remove",
    "deletingRow": "Removing…",
    "rowSaved": "Row saved",
    "rowDeleted": "Removed from feed",
    "deleteRowConfirm": "Remove this SKU from the feed? Your Shopify product will not be deleted.",
    "noEdits": "No changes to apply",
    "csvDownloaded": "CSV downloaded",
    "snapshots": "Previous versions",
    "snapshotsHelp": "Read-only snapshots. Restore replaces the live feed URL.",
    "noSnapshots": "No snapshots yet — they appear after the next update.",
    "restore": "Restore as current",
    "restored": "Snapshot restored to current feed",
    "markets": {
      "US": { "title": "United States (English) {{ccy}}", "subtitle": "United States (English)" },
      "DE": { "title": "Germany (German) {{ccy}}", "subtitle": "Germany (German)" },
      "FR": { "title": "France (French) {{ccy}}", "subtitle": "France (French)" },
      "ES": { "title": "Spain (Spanish) {{ccy}}", "subtitle": "Spain (Spanish)" },
      "IT": { "title": "Italy (Italian) {{ccy}}", "subtitle": "Italy (Italian)" }
    }
  },
  "targets": {
    "platforms": "Where to advertise",
    "markets": "Target markets",
    "marketsWithCcy": "Target markets (store {{ccy}})",
    "marketsHelp": "Default US (USD). For each market, set Shopify presentment to that currency; mismatches are blocked."
  },
  "images": {
    "heading": "Pick an ad main image",
    "help": "Changes only the ad feed image, not your Shopify product page. “Recommended” is usually cleaner; “Not recommended” often means wholesale stock.",
    "loading": "Loading product images…",
    "empty": "No candidates found — upload product images in Shopify first.",
    "recommended": "Recommended",
    "risky": "Not recommended",
    "save": "Use selected image & regenerate feed",
    "saving": "Saving…",
    "cancel": "Cancel"
  },
  "products": {
    "heading": "Products in scope ({{selected}}/{{total}}, {{variants}} variants)",
    "help": "Photos first — check what goes into the feed.",
    "search": "Search title, type, brand…",
    "selectAll": "Select all",
    "deselectAll": "Deselect all",
    "colSelect": "Include",
    "colProduct": "Product",
    "colType": "Type",
    "colVariants": "Variants",
    "colInventory": "Inventory",
    "colStatus": "Status",
    "colAdImage": "Ad image",
    "colActions": "Actions",
    "editInShopify": "Edit this in Shopify",
    "vendor": "Shopify vendor: {{vendor}}",
    "variantCount": "{{n}} variants",
    "hintColor": "Needs color",
    "hintSize": "Needs size",
    "hintImage": "Change ad image",
    "hintWording": "Wording to review",
    "needsInListHint": "{{n}} products need fixes — pinned to the top.",
    "fixThis": "Fix all variants",
    "fixThisHint": "“Fix all variants” checks every SKU below, then fill color/size once above.",
    "fixColorBtn": "Add color",
    "fixSizeBtn": "Add size",
    "fixWordingBtn": "Edit wording in Shopify",
    "noStock": "Out of stock",
    "active": "Active",
    "changeAdImage": "Change ad image",
    "afterGenerate": "Pick after generate",
    "selectA11y": "Select {{title}}",
    "loading": "Loading products…"
  },
  "tags": {
    "colorMulti": "Color: Multicolor (smart fill)",
    "sizeOne": "Size: One Size (smart fill)",
    "colorExtracted": "Color: {{value}} (from copy)",
    "colorAi": "Color: {{value}} (AI)",
    "colorDone": "Color filled",
    "sizeExtracted": "Size: {{value}} (from copy)",
    "sizeDone": "Size filled",
    "noGtin": "No-ID path (add real barcode in Shopify if you have one)",
    "adult": "Marked adult (account safety)"
  },
  "msg": {
    "apiNotConfigured":
      "API URL is not configured. Re-run local_iframe_stack.sh and deploy, or set BACKEND_URL on the server.",
    "bootIncomplete": "Store connection incomplete: {{detail}}",
    "bootFailed": "Store connection failed: {{detail}}",
    "loadProductsFailed": "Failed to load products: {{detail}}",
    "needProduct": "Select at least one product",
    "needPlatformMarket": "Select at least one platform and one market",
    "needBrand": "Confirm an ad brand below first. Apparel Google needs brand; empty brand often fails as Missing brand.",
    "quotaShort": "Not enough quota: need {{need}}, {{left}} left. Please upgrade.",
    "checking": "Check in progress. We clean titles, fill color/size, and open the no-ID path.",
    "genFailed": "Generation failed",
    "blockedOnly": "Feed not generated: {{countries}} blocked for currency mismatch. Align Shopify presentment with the selected markets and retry.",
    "doneFatal": "Check done: feed generated, but {{fatals}} high-risk items remain. Review the list below — not “approved” yet.",
    "doneWarn": "Check done: auto-fixed {{auto}} items; {{warn}} still need a spot-check before Google.",
    "doneOk": "Check done: fields look complete — add the feed link in Google Merchant Center.",
    "doneMergeOk": "This product was added to the current feed (other items kept).",
    "regenConfirm": "{{n}} selected product(s) are already in the feed. Regenerate and overwrite them? (Uses quota again.)",
    "mergeConfirm": "Add {{n}} product(s) into the current feed? Existing items stay.",
    "alsoBlocked": " Also {{count}} market(s) blocked for currency.",
    "noFeed": "Feed not generated: no writable country or products.",
    "genFailedDetail": "Generation failed: {{detail}}",
    "needSku": "Select SKUs to fix first",
    "patchOk": "✅ Updated {{updated}} variants{{missing}}, feed refreshed",
    "patchMissing": ", {{count}} SKUs not found",
    "patchFailed": "Bulk update failed: {{detail}}",
    "imagesLoadFailed": "Failed to load product images: {{detail}}",
    "needImage": "Select a main image",
    "imageSaved": "✅ {{sku}} ad image updated, feed refreshed",
    "imageFailed": "Image update failed: {{detail}}",
    "complianceDone": "Site check: {{light}} (pass {{pass}} · suggestions {{warn}} · missing {{fail}})",
    "complianceFailed": "Site check failed: {{detail}}",
    "brandEmpty": "Enter an ad brand before confirming. Apparel Google needs brand.",
    "brandSaved": "Ad brand saved as “{{brand}}”. Feed generate will write g:brand.",
    "brandFailed": "Failed to save ad brand: {{detail}}",
    "lightGreen": "green",
    "lightYellow": "yellow",
    "lightRed": "red"
  },
  "rules": {
    "C01": {
      "msg": "Apparel missing color — filled Multicolor",
      "sug": "If the product has a real color, set Color on the Shopify variant and regenerate"
    },
    "C02": {
      "msg": "Extracted color from copy → {{after}}",
      "sug": ""
    },
    "S01": {
      "msg": "Apparel/footwear missing size — filled One Size",
      "sug": "If there is a real size, add Size on the Shopify variant and regenerate"
    },
    "S05": {
      "msg": "Size alias normalized to One Size (was: {{before}})",
      "sug": ""
    },
    "S02": {
      "msg": "Defaulted age_group=adult",
      "sug": "For kidswear, set kids/toddler/infant in the store"
    },
    "S03": {
      "msg": "Defaulted condition=new",
      "sug": ""
    },
    "S04": {
      "msg": "Aligned gender={{after}}",
      "sug": "Adjust to female / male / unisex from category or title"
    },
    "ID01": {
      "msg": "No barcode — opened no-ID path (identifier_exists=no)",
      "sug": "Add GTIN if you have UPC/EAN; otherwise keep no-ID and a valid brand"
    },
    "ID02": {
      "msgReplaced": "Brand contained myshopify.com — replaced with store brand {{after}}",
      "msgWarn": "Brand contains myshopify.com ({{before}}) — set a real store brand",
      "sug": "Set default_brand; do not use *.myshopify.com as brand"
    },
    "M01": {
      "msg": "Material translated to English → {{after}}",
      "sug": "Confirm it matches the product"
    },
    "M03": {
      "msg": "Inferred material from title/fabric → {{after}}",
      "sug": "Add accurate fabric in Shopify"
    },
    "M02": {
      "msg": "Apparel missing material — GMC may warn about incomplete attributes",
      "sug": "Add fabric in Shopify (e.g. Cotton / Polyester) and regenerate"
    },
    "D01": {
      "msg": "Description was mostly Chinese — used English summary fallback",
      "sug": "Add English product details to improve Shopping quality"
    },
    "D02": {
      "msg": "Description formatted; attribute labels Anglicized where possible",
      "sug": ""
    },
    "D03": {
      "msg": "Description had heavy Chinese — replaced with English summary",
      "sug": "Add English details in Shopify and regenerate"
    },
    "T01": {
      "msg": "Title is empty",
      "sug": "Add a valid product title and regenerate"
    },
    "I01": {
      "msg": "Main image is empty",
      "sug": "Upload a main image in Shopify and regenerate"
    },
    "I02": {
      "msg": "Main image is not an absolute URL",
      "sug": "Use an https image URL"
    },
    "I03": {
      "msg": "Main image may be from a wholesale source ({{detail}})",
      "sug": "Use “Change image” below to pick a clean photo from the product gallery"
    },
    "P02": {
      "msg": "Price is invalid or zero",
      "sug": "Set a valid price in Shopify and regenerate"
    },
    "L01": {
      "msg": "Product link is invalid",
      "sug": "Check storefront URL and product handle"
    },
    "V01": {
      "msg": "Apparel should include a color",
      "sug": "Set Color on the Shopify variant"
    },
    "VA01": {
      "msgFallback": "Variant missing color — filled Multicolor",
      "msgClean": "Color cleaned → {{after}}",
      "sug": ""
    },
    "VA02": {
      "msgFallback": "Apparel missing size — filled One Size",
      "msgClean": "Size cleaned → {{after}}",
      "sug": ""
    },
    "VA03": {
      "msg": "Filled size_system=US, size_type=Regular",
      "sug": ""
    },
    "VA04": {
      "msg": "Missing Shopify Variant ID — link cannot target color/size; re-sync before advertising",
      "sug": "Re-sync the product in Shopify, confirm the variant exists, then regenerate"
    },
    "IMG01": {
      "msg": "Watermark removed and main image replaced",
      "sug": ""
    },
    "IMG02": {
      "msgEmpty": "Main image empty — cannot remove watermark",
      "msgFail": "Main image may have a watermark; processing failed — please replace",
      "sugEmpty": "Upload at least one product image",
      "sugFail": "Replace with a clean product photo"
    },
    "AD01": {
      "msg": "Set adult=yes for sensitive category (account safety)",
      "sug": "Ads will show to adults only — protects the account"
    },
    "SEN": {
      "soft": "Sensitive phrasing softened ({{id}})",
      "flag": "Adult-oriented signal detected ({{id}})",
      "block": "High-risk sensitive content ({{id}}) — do not advertise on GMC until reviewed",
      "sug": "Update Shopify copy to match; avoid advertising FATAL items"
    }
  },
  "complianceChecks": {
    "POL_SCAN": {
      "unknown": "Could not read Shopify policies via the app (missing read_legal_policies). Check Settings → Policies manually."
    },
    "policyLabel": {
      "POL_REFUND": "Refund policy",
      "POL_PRIVACY": "Privacy policy",
      "POL_SHIPPING": "Shipping policy",
      "POL_TERMS": "Terms of service"
    },
    "policyMissing": "Missing {{label}}",
    "policyMissingSug": "Create and publish it in Shopify Settings → Policies",
    "policyPresent": "{{label}} is present",
    "policyPresentSug": "Make sure the footer menu links to this policy page",
    "policyWeak": "{{label}} may be thin or placeholder-like",
    "SITE_HTTPS": {
      "pass": "Store URL uses HTTPS",
      "fail": "Store URL is not HTTPS",
      "failSug": "Use a custom domain with SSL in Shopify"
    },
    "SITE_REACHABLE": {
      "pass": "Homepage is reachable",
      "http": "Homepage returned HTTP {{code}}",
      "httpSug": "Confirm the store is not password-protected and the domain is public",
      "down": "Could not probe homepage (timeout or network error)",
      "downSug": "Open the storefront in a browser to confirm"
    },
    "FOOT": {
      "pass": "{{label}} is linked in the footer",
      "warn": "{{label}} is linked on the page but not inside <footer>",
      "warnSug": "Online Store → Navigation → Footer menu — add the policy link",
      "fail": "{{label}} is configured but not linked on homepage/footer",
      "failSug": "Add the policy page to the Footer menu (GMC expects it to be discoverable)"
    },
    "FOOT_CONTACT": {
      "pass": "Contact is linked in the footer",
      "warn": "Contact is linked on the page but not inside <footer>",
      "warnSug": "Add the Contact page to the Footer menu"
    },
    "FOOT_SCAN": {
      "warn": "Could not parse homepage HTML; skipped footer link checks"
    },
    "CONTACT_PAGE": {
      "pass": "Found a contact page",
      "warn": "No /pages/contact, but store has email/phone in admin",
      "warnSug": "Create a Contact page and link it in the footer (GMC often checks visible contact info)",
      "fail": "No Contact page and no visible contact details",
      "failSug": "Add a Contact page with email + phone or address, and put it in the footer menu"
    },
    "CURR": {
      "pass": "{{country}} market: store currency matches Feed target (or is usable)",
      "warn": "{{country}} needs matching presentment currency — align Shopify Markets before generating",
      "warnSug": "In Shopify Markets / presentment currency, match the target market, then regenerate"
    }
  }
},
  "zh-CN": {
  "name": "AdFeed AI",
  "welcome": "AdFeed AI — Google 购物 Feed",
  "gmc": {
    "issuesTitle": "过审问题",
    "issuesHint": "Feed 进入 Merchant Center 后，可在此同步拒审原因。仅支持手动同步。",
    "oauthNotConfigured": "服务器尚未配置 Google OAuth（需设置 GOOGLE_OAUTH_*）。",
    "connectLater": "服务器配好 OAuth 后再连接 Google。",
    "connect": "连接 Google",
    "disconnect": "断开连接",
    "refreshMerchants": "刷新账号",
    "merchant": "Merchant 账号",
    "selectMerchant": "选择…",
    "sync": "同步问题",
    "empty": "暂无缓存问题。连接 Google 后点同步。",
    "unmatched": "未匹配 offer",
    "matchStats": "已匹配 {{matched}} · 未匹配 {{unmatched}}"
  },
  "ads": {
    "metricsTitle": "广告效果",
    "metricsHint": "有商品级数据时展示 Shopping 花费/点击。只读；仅手动同步。",
    "needGoogleFirst": "请先在「过审问题」连接 Google。",
    "connectAds": "授权读取 Ads",
    "customerId": "Ads 客户 ID",
    "sync": "同步效果",
    "devTokenMissing": "服务器未配置 GOOGLE_ADS_DEVELOPER_TOKEN，无法同步效果。",
    "degraded": "暂无商品级数据，已降级为系列/账户汇总。",
    "productLevel": "{{n}} 条商品级记录",
    "rowStats": "{{imps}} 展示 · {{clicks}} 点击 · {{cost}}",
    "empty": "暂无缓存效果数据。"
  },
  "meta": {
    "catalogTitle": "Meta 目录",
    "catalogHint": "连接 Meta，选择 Catalog，并把本店 Meta Feed URL 挂到定时抓取。",
    "oauthNotConfigured": "服务器尚未配置 Meta OAuth（需设置 META_*）。",
    "connect": "连接 Meta",
    "disconnect": "断开连接",
    "catalog": "目录",
    "selectCatalog": "选择…",
    "refreshCatalogs": "刷新目录",
    "attachFeed": "挂接 Feed URL",
    "attachOk": "已创建定时 Feed {{feedId}}，Meta 将拉取你的 Meta Feed。",
    "syncIssues": "同步拒审问题",
    "issuesEmpty": "暂无 Meta 拒审缓存。连接后点同步。",
    "unmatched": "未匹配 offer",
    "matchStats": "已匹配 {{matched}} · 未匹配 {{unmatched}}"
  },
  "tiktok": {
    "shopTitle": "TikTok 小店",
    "shopHint": "连接 TikTok Shop，选择店铺，并登记本店 CSV Feed URL（不编造重量）。",
    "oauthNotConfigured": "服务器尚未配置 TikTok OAuth（需设置 TIKTOK_*）。",
    "connect": "连接 TikTok",
    "disconnect": "断开连接",
    "shop": "店铺",
    "selectShop": "选择…",
    "refreshShops": "刷新店铺",
    "attachFeed": "登记 Feed URL",
    "attachOk": "已登记 CSV：{{url}}",
    "syncIssues": "同步上架问题",
    "issuesEmpty": "暂无 TikTok 上架问题缓存。连接后点同步。",
    "unmatched": "未匹配 offer",
    "matchStats": "已匹配 {{matched}} · 未匹配 {{unmatched}}"
  },
  "cta": {
    "generate": "生成 Feed",
    "create": "生成 Feed",
    "updateWide": "生成 Feed",
    "update": "生成 Feed",
    "generating": "处理中…",
    "needBrand": "请先点下方「确认品牌」",
    "selectVisible": "全选当前列表",
    "meta": "已选 {{n}} 件 · {{platform}} · {{market}}",
    "sub": "将 {{n}} 件写入 Feed"
  },
  "genModal": {
    "title": "确认生成 Feed",
    "summaryNew": "将为所选 {{n}} 件商品生成 Feed。",
    "summaryMerge": "将把 {{n}} 件合并进当前 Feed（其他商品保留）。",
    "summaryOverwrite": "已选 {{n}} 件 · 其中 {{overwrite}} 件已在 Feed 中，会被覆盖。",
    "uncheckHint": "可取消勾选，跳过不想这次生成的商品。",
    "willOverwrite": "已在 Feed · 将覆盖（{{n}} 个变体）",
    "willAdd": "新商品 · 将加入 Feed",
    "cancel": "取消",
    "confirm": "生成 {{n}} 件",
    "close": "关闭"
  },
  "hub": {
    "title": "Feed Generator Hub",
    "panel": "HUB PANEL",
    "subtitle": "先选商品范围（必须看见图），再选市场，一键生成可交给 Google 的 Feed。",
    "scopeHeading": "1. 选择商品同步范围",
    "scopeHelp": "点「全部在售」「未分类」或某个分类，筛选下方商品。",
    "productsInScope": "本范围：已选 {{selected}} / 共 {{total}}",
    "emptyScope": "这个范围里没有商品。",
    "productListScroll": "共 {{n}} 件 — 在列表内上下滚动查看。",
    "productListPrev": "上一页",
    "productListNext": "下一页",
    "productListPage": "第 {{from}}–{{to}} 件 / 共 {{n}} 件",
    "marketHeading": "2. 目标渠道与市场",
    "statsHeading": "一眼看懂",
    "statsHint": "来自上次生成结果 — 不是 Google 已过审。",
    "activeFeeds": "活跃 Feed",
    "checklistHeading": "店铺待办",
    "checklistHelp": "只列未完成项。到 Shopify 改完后，再点「重新检查」。",
    "feedsHeading": "复制到 Merchant Center",
    "createHeading": "3. 生成 Feed",
    "createHint": "通栏主按钮。",
    "scopeThenMarket": "下一步：在下方选国家，然后点「生成 Feed」。",
    "needProducts": "请先在下方勾选要进 Feed 的商品。",
    "productListHeading": "本范围商品明细（可再勾选）",
    "setupCard": "生成广告 Feed",
    "productsCard": "选择进 Feed 的商品"
  },
  "overview": {
    "heading": "Feed 状态",
    "needsAttention": "要处理 · {{n}}",
    "ready": "已可投 · {{n}}",
    "selected": "本范围已选 · {{n}}",
    "panelNeeds": "要处理",
    "panelReady": "已可投",
    "panelSelected": "本范围已选",
    "kpiNeeds": "待改商品",
    "kpiNeedsHint": "缺色、缺码、主图或敏感词，需要你改",
    "kpiReady": "本批商品",
    "kpiReadyHint": "已写入这一市场 Feed 的条数（不是 Google 已过审）",
    "kpiReadyUnknown": "—",
    "kpiReadyUnknownHint": "生成后才有条数",
    "kpiFeeds": "广告链接",
    "kpiFeedsHint": "已生成、可复制到广告后台的链接",
    "kpiTapHint": "",
    "kpiNeedsAction": "去改这 {{n}} 件",
    "kpiNeedsActionEmpty": "暂无待改",
    "kpiNeedsCollapse": "收起",
    "kpiNeedsStoreOnly": "没有商品待改。品牌、币种、网站项请看下方店铺待办。",
    "kpiReadyAction": "看明细",
    "kpiFeedsAction": "复制链接",
    "kpiFeedsCollapse": "收起",
    "noneYet": "还没有广告链接 — 先勾选商品，再生成。",
    "emptyNeeds": "目前没有需要改的商品。",
    "showFeeds": "Feed 链接在下方。",
    "storeBrandGate": "生成前请先确认广告品牌。",
    "storeCurrencyGate": "有 {{count}} 个市场因币种被挡住 — 请到 Shopify 改币种或换市场。",
    "adjustScope": "调整选品并更新",
    "hideScope": "收起选品",
    "storeTodos": "店铺待办",
    "storeTodosHelp": "只显示未完成项。请到 Shopify 改，或在下方确认品牌。"
  },
  "scope": {
    "heading": "1. 选哪些货",
    "help": "先点类型，再看图勾选 — 应能认出每件衣服。",
    "allActive": "全部在售（{{n}}）",
    "uncategorized": "未分类（{{n}}）",
    "typeChip": "{{type}}（{{n}}）",
    "myStoreType": "我的商店",
    "inScope": "已选 {{selected}} · 本范围 {{total}}",
    "selectScope": "全选本范围",
    "needsChip": "待改（{{n}}）"
  },
  "intro": {
    "heading": "上广告前，先做一轮安检",
    "body": "我们不会承诺 Google 一定批准。会先帮你把标题、颜色尺码、无码通道、主图整理成购物广告能吃的 Feed，你看懂改过什么，再把链接交给 Merchant Center。缺真条码或成本价时不会编假值，可在下方说明处按需补。",
    "note": "提交后 Google 常显示 Limited / Pending initial review，那是首次审核排队，一般要几个工作日，不是 App 失败。"
  },
  "setup": {
    "heading": "2. 投放到哪里",
    "platforms": "广告平台",
    "markets": "投放国家",
    "marketsWithCcy": "投放国家",
    "storeCcy": "本店结算是 {{ccy}}。Feed 价必须等于该国落地页上买家看到的币种和金额；不会按汇率改价。",
    "marketsHelp": "按钮上的币种是该国页面应展示的货币。例如投德国，请先在 Shopify 市场开欧元展示价，再勾选德国。",
    "marketLocked": "请先在 Shopify 市场开通{{country}}并显示{{expected}}",
    "needOneMarket": "至少保留一个国家。",
    "checkingMarket": "正在确认该国展示货币…",
    "country": {
      "US": "美国",
      "CA": "加拿大",
      "GB": "英国",
      "DE": "德国",
      "FR": "法国",
      "ES": "西班牙",
      "IT": "意大利",
      "NL": "荷兰",
      "BE": "比利时",
      "AT": "奥地利",
      "IE": "爱尔兰",
      "PT": "葡萄牙",
      "FI": "芬兰",
      "SE": "瑞典",
      "NO": "挪威",
      "DK": "丹麦",
      "CH": "瑞士",
      "PL": "波兰",
      "AU": "澳大利亚",
      "NZ": "新西兰",
      "JP": "日本",
      "KR": "韩国",
      "SG": "新加坡",
      "HK": "香港",
      "TW": "台湾",
      "QA": "卡塔尔",
      "AE": "阿联酋"
    },
    "ccy": {
      "USD": "美元",
      "EUR": "欧元",
      "GBP": "英镑",
      "CAD": "加元",
      "AUD": "澳元",
      "NZD": "新西兰元",
      "JPY": "日元",
      "KRW": "韩元",
      "SGD": "新加坡元",
      "HKD": "港币",
      "TWD": "新台币",
      "QAR": "卡塔尔里亚尔",
      "AED": "阿联酋迪拉姆",
      "SEK": "瑞典克朗",
      "NOK": "挪威克朗",
      "DKK": "丹麦克朗",
      "CHF": "瑞士法郎",
      "PLN": "波兰兹罗提"
    },
    "needOneMarket": "至少保留一个国家。",
    "checkingMarket": "正在确认该国展示货币…",
    "pickPlatforms": "选择渠道",
    "pickMarkets": "选择市场",
    "marketsSelected": "已选 {{n}} 个国家",
    "searchMarkets": "搜索国家…",
    "noMarketMatch": "没有匹配的国家",
    "loadingMarkets": "正在加载可用国家…",
    "noCompatibleMarkets": "暂无可生成 Feed 的国家。请在 Shopify Markets 启用目标市场，并确保该国页面展示对应货币。"
  },
  "storeWarnings": {
    "heading": "店铺需要设置的项",
    "help": "这些是店铺侧提醒，方便你少踩坑；真正生成 Feed 仍以上方勾选的商品为准。"
  },
  "pipeline": {
    "heading": "正在生成",
    "headingDone": "本轮已生成",
    "headingCollapsed": "已生成",
    "doneHint": "请优先改下方待改商品的颜色或尺码。",
    "stay": "请留在此页。结束后会标出改过颜色、尺码的商品，你可以一键改回真实规格。",
    "hideSteps": "收起步骤",
    "showSteps": "展开五步",
    "badgeDone": "已完成",
    "badgeActive": "进行中",
    "badgeWait": "等待",
    "steps": {
      "title": {
        "label": "标题",
        "copy": "正在把堆砌的货源标题，改成 Google 购物能读懂的结构…"
      },
      "category": {
        "label": "类目",
        "copy": "正在给商品对上标准类目，避免放到错误货架…"
      },
      "variant": {
        "label": "颜色 / 尺码",
        "copy": "正在检查每个色、每个码是否齐全；缺的会先智能补上，你可以再改…"
      },
      "id": {
        "label": "条码 / 无码通道",
        "copy": "没有真条码会开通无码通道（不编假码）；有 UPC/EAN 可到 Shopify 变体条码补上…"
      },
      "image": {
        "label": "广告主图",
        "copy": "正在检查主图是否像批发站原图，方便你换成自己店里的干净实拍…"
      }
    }
  },
  "quota": {
    "heading": "配额",
    "remaining": "{{used}} / {{total}}（剩余 {{left}}）",
    "estimate": "预估消耗：{{skus}} SKU × {{platforms}} 平台 × {{markets}} 市场 =",
    "insufficient": " — 配额不足，请升级"
  },
  "billing": {
    "current": "套餐：{{plan}} · 剩余 {{left}} / {{total}} 次生成",
    "headerQuota": "{{plan}} · {{left}} / {{total}}",
    "plan_free": "免费",
    "plan_starter": "Starter（$14.99/月，50 次）",
    "plan_growth": "Growth（$39/月，200 次）",
    "chooseStarter": "改用 Starter",
    "chooseGrowth": "改用 Growth",
    "approveInShopify": "去 Shopify 确认扣费",
    "approveHint": "请点「去 Shopify 确认扣费」，批准后再回到本页。",
    "subscribeFailed": "无法开通套餐：{{detail}}",
    "plans": {
      "open": "升级套餐",
      "back": "返回",
      "pageTitle": "选择套餐",
      "pageIntro": "对比免费 / Starter / Growth。选付费套餐后会跳到 Shopify 确认扣费。",
      "howQuota": "配额按「父商品 × 广告平台 × 市场」计（不是按变体）。一件衣服 5 色 × 5 码，Google+美国仍只算 1 次。",
      "currentBadge": "当前",
      "included": "已包含",
      "choose": "选用 {{plan}}",
      "starting": "开通中…",
      "free": {
        "name": "免费",
        "price": "$0 / 月",
        "quota": "每月 3 次生成",
        "blurb": "适合先跑通小目录。"
      },
      "starter": {
        "name": "Starter",
        "price": "$14.99 / 月",
        "quota": "每月 50 次生成",
        "blurb": "适合常态跑 Google Shopping。"
      },
      "growth": {
        "name": "Growth",
        "price": "$39 / 月",
        "quota": "每月 200 次生成",
        "blurb": "适合多平台 / 多市场。"
      }
    }
  },
  "brand": {
    "heading": "广告品牌（写入 Feed）",
    "help": "这是整店写入 Feed 的 g:brand（消费者认的店牌）。Shopify 商品上的 Vendor 经常是供应商名（如 eprolo），不会自动当广告品牌。确认过一次即可；只有要改名时再点下面按钮。",
    "warn": "尚未确认广告品牌。请填写后点「确认品牌」，否则无法开始安检生成 Feed（避免 Missing brand 拒审）。",
    "confirmed": "广告品牌：{{brand}}",
    "label": "广告品牌",
    "placeholder": "例如你的店名或自有品牌",
    "saving": "保存中…",
    "confirm": "确认品牌",
    "update": "更新品牌",
    "change": "更改",
    "cancelEdit": "取消"
  },
  "merchantData": {
    "heading": "条码与成本（商家可选）",
    "help": "不挡住生成 Feed。我们不会编假条码或假成本；有真实数据再补，广告匹配和利润报表会更好。",
    "gtinTitle": "条码 / GTIN",
    "gtinShort": "可选；有真 UPC/EAN 再到 Shopify 变体填，勿编假码。",
    "gtinBody": "没有条码也能投：会走无码通道，并保留上方确认的广告品牌。若包装或厂家有真 UPC/EAN，请到 Shopify → 商品 → 对应变体的「条码」填上；下次生成会写入 g:gtin。没有真码请留空，不要随便编一串数字。",
    "cogsTitle": "成本价（COGS）",
    "cogsShort": "可选；没有就留空，勿编假成本。",
    "cogsBody": "不是免费展示上架的强制字段，空着也能进 Feed。有真实进货成本时，可在 Shopify 变体「成本价」填写，便于日后看利润报表；没有就留空，请勿填估计数凑字段。"
  },
  "compliance": {
    "heading": "网站是否适合投广告",
    "help": "检查政策页、页脚链接、HTTPS、所选市场币种。这是 Google 审店时也会看的，不挡住生成 Feed。",
    "run": "重新检查",
    "running": "检查中…",
    "summary": "通过 {{pass}} · 建议 {{warn}} · 缺失 {{fail}}",
    "colId": "项",
    "colStatus": "状态",
    "colNote": "说明",
    "lightGreen": "通过",
    "lightYellow": "有建议",
    "lightRed": "有缺失",
    "statusWarn": "建议",
    "statusFail": "缺失",
    "allPass": "这项检查暂无待办。",
    "needRun": "点「一键诊断」检查政策页、页脚链接和 HTTPS。",
    "currencyOk": "所选市场币种与店铺一致（或可用）",
    "openHeading": "待处理（{{n}}）",
    "doneHeading": "已完成（{{n}}）",
    "doneBadge": "完成",
    "fixInShopify": "在 Shopify 中打开",
    "fixMenus": "打开页脚菜单",
    "fixLegal": "打开政策设置",
    "fixMarkets": "打开 Markets",
    "fixPages": "打开页面"
  },
  "currency": {
    "mismatchBanner": "已选 {{markets}}，店铺当前是 {{shop}}。请在 Shopify 把对应展示改成一致后再生成（App 只做检测，不会自动换汇）。",
    "blockedHeading": "币种不一致（已拦截）",
    "shopNeeds": "店币 {{shop}} → 需要 {{expected}}",
    "fixHint": "请在 Shopify 将展示币种改成与所选市场一致后再生成。"
  },
  "quality": {
    "heading": "本轮详情",
    "lightGreen": "可以交给 Google",
    "lightYellow": "已帮你补全，建议抽查",
    "lightRed": "有高风险，先看再投",
    "bodyGreen": "必填项看起来齐了。下一步：复制下方 Feed 链接，粘贴到 Google Merchant Center。批准仍由 Google 决定，新店常见要等几天初审。",
    "bodyGreenShort": "可以提交了。把上方链接贴进 Merchant Center；Google 初审常要几天。",
    "bodyYellow": "已自动处理 {{auto}} 项（例如缺色/缺码兜底、无条码走无码通道）。还有 {{warn}} 项建议抽查。无码或未填成本价不是拒登原因；有真条码/成本可到 Shopify 补。这不是「已经过审」，是「可以交，但请先看一眼」。",
    "bodyYellowShort": "已自动处理 {{auto}} 项。其中 {{review}} 个需要真实颜色/尺码或主图——下方勾选后一次改完（不扣配额）。",
    "bodyRed": "有 {{fatals}} 条高风险仍写进了 Feed。请先处理下方红色清单；没改之前不建议当成可投放广告。",
    "counts": "自动处理 {{auto}} · 建议抽查 {{warn}} · 高风险 {{fatals}}",
    "missingVariantId": "{{count}} 个变体缺少 Shopify Variant ID，链接无法定位到具体色/码。请重新同步商品后再生成；修好前请勿投放这些 SKU（已禁止使用内部假 ID）。",
    "logTitle": "优化日志",
    "detailsHeading": "技术详情",
    "expandDetails": "展开详情",
    "collapse": "收起",
    "expand": "展开前 {{n}} 条",
    "logMore": "另有 {{n}} 条自动处理未展开",
    "titleCompare": "标题怎么变好看了",
    "titleCompareHelp": "店内原标题 → 购物广告标题。",
    "titleBefore": "改前：{{title}}",
    "titleAfter": "广告标题：{{title}}",
    "confirmHeading": "要处理 — 先改你想改的，再更新 Feed",
    "confirmHelp": "这些是建议，不是锁死。可在此改色/码/图，或去 Shopify 编辑。不必清零也能更新 Feed。",
    "bulkHelp": "点「改全部规格」才会一次改多行。点某一行的「改尺码」只改那一行。",
    "bulkHint": "提示：点「全选」→ 输入真实颜色或尺码 → 点应用。",
    "applying": "应用中…",
    "sensitiveTitle": "敏感文案 · {{count}}",
    "sensitiveHelp": "已软化或标记 adult；需要可到 Shopify 再改。",
    "colSku": "SKU",
    "colProduct": "商品",
    "colRule": "规则",
    "colNote": "说明",
    "colField": "字段",
    "colResult": "结果",
    "imageTitle": "主图 · {{count}}",
    "imageHelp": "选一张更干净的广告图（不改 Shopify 原图）。",
    "changeImage": "换主图",
    "mcTitle": "缺颜色 · Multicolor · {{count}} 个",
    "osTitle": "缺尺码 · One Size · {{count}} 个",
    "selectBucket": "全选",
    "bulkTitle": "一次改选中的 {{count}} 个",
    "color": "颜色",
    "colorPh": "如 Black",
    "applyColor": "应用颜色",
    "oneSizeBtn": "保持 One Size",
    "size": "尺码",
    "sizePh": "如 M / L / XL",
    "applySize": "应用尺码",
    "clearSelection": "清空",
    "checklist": {
      "shipping": "上传 Google 前确认目标国运费已在 Merchant Center 配置",
      "claim": "确认网站已认领且商品页可公开访问",
      "fatal": "若仍有红色 FATAL，上传需自行承担拒审风险"
    }
  },

  "workbench": {
    "heading": "智能 Feed 优化工作台",
    "search": "搜索商品",
    "channels": "渠道",
    "itemsInFeed": "Feed {{n}} 条",
    "tagPending": "待生成",
    "actionGenerateFeed": "生成到 Feed",
    "tagInFeed": "Feed · {{n}}变体",
    "tagFailed": "生成失败",
    "defectsLine": "建议补充：{{list}}",
    "fixThenGenerate": "修复后生成",
    "fixOptional": "可选修复",
    "edit": "编辑Feed",
    "statusReady": "Ready",
    "statusMissing": "Missing Info",
    "statusWarn": "需检查",
    "statusPending": "未生成",
    "statusPendingHint": "还没写入当前 Feed — 点本行「生成到 Feed」（会保留 Feed 里已有商品）。",
    "editAfterGenerate": "请先生成",
    "generateOne": "生成到Feed",
    "tableHelp": "Ready / Missing Info＝已在 Feed，可点「编辑 Feed」。未生成＝点本行「生成到 Feed」，或勾选多件后点上方「生成/更新」。",
    "needsChip": "要处理 · {{n}}",
    "needsBanner": "有 {{n}} 件商品在 Shopify 变体里缺颜色和/或尺码 — 可先去店铺补全，或生成后再改。点上方筛选只看这些。",
    "hintMissingColor": "缺颜色",
    "hintMissingSize": "缺尺码",
    "hintMissingImage": "主图建议换一张更干净的",
    "fixColorTitle": "添加颜色：{{title}}",
    "fixSizeTitle": "添加尺码：{{title}}",
    "fixColorHelp": "填写真实颜色（如 Black）。会应用到这件商品的变体。",
    "fixSizeHelp": "填写真实尺码（如 M / One Size）。会应用到这件商品的变体。",
    "fixColorPrompt": "这件商品缺颜色 — 填一次并点「应用到全部 SKU」，再保存。",
    "fixSizePrompt": "这件商品缺尺码 — 填一次并点「应用到全部 SKU」，再保存。",
    "applyToAllSkus": "应用到全部 SKU",
    "bulkColorApplied": "已把颜色 {{value}} 填到全部 SKU — 请再点保存写回 Feed。",
    "bulkSizeApplied": "已把尺码 {{value}} 填到全部 SKU — 请再点保存写回 Feed。",
    "fixNeedValue": "请先填写内容",
    "fixNoSkus": "找不到这件商品的变体 — 请先同步或生成。",
    "fixSavedInFeed": "已保存并更新当前 Feed。",
    "fixSavedShopify": "已写入 Shopify 商品选项 — 可点本行「生成到 Feed」。",
    "fixSavedNeedGenerate": "已写到变体 — 请再点本行「生成到 Feed」写入 XML。",
    "fixSave": "保存",
    "emptyProducts": "还没有商品",
    "compliance": "网站自查建议",
    "complianceSummary": "{{warn}} 条建议",
    "complianceSummaryClear": "暂无建议",
    "complianceSummaryUnknown": "{{unknown}} 项未能自动检测",
    "complianceEmpty": "正在检查店铺政策与联系信息…",
    "liveFeed": "当前 XML Feed",
    "editingFeed": "正在编辑",
    "editingFeedHint": "切换国家可编辑对应 XML；上方「市场」多选仅用于批量生成。",
    "needGenerate": "请先生成 Feed，才能预览和编辑条目",
    "drawerTitle": "编辑 Feed 属性：{{title}}",
    "drawerHint": "只改购物广告 Feed（标题 / 色 / 码 / 主图），不改 Shopify 商品页。",
    "noFeedItems": "这件商品还不在当前 Feed 里。请点本行「生成到 Feed」，或勾选后点上方「生成/更新」。",
    "close": "关闭",
    "cancel": "取消",
    "saveApply": "保存并应用到当前 Feed",
    "deleteFeedRow": "删除 Feed"
  },
  "feeds": {
    "heading": "多语言 Google Shopping Feed 链接",
    "help": "复制链接到 Google Merchant Center。提交后 Limited 多为初审排队。",
    "items": "{{count}} 个商品",
    "listedCount": "Feed 条数",
    "synced": "已生成",
    "preparing": "尚未生成",
    "urlLabel": "Feed 链接",
    "copy": "复制链接",
    "copyShort": "复制",
    "copied": "已复制链接",

    "viewItems": "查看 / 编辑条目",
    "hidePreview": "收起条目",
    "downloadCsv": "下载 CSV",
    "openXml": "打开 XML",
    "openRawXml": "原始 XML",
    "editFeed": "查看并编辑 Feed",
    "editAllFeed": "编辑全部 Feed",
    "backToWorkbench": "返回工作台",
    "pageHeading": "Feed 编辑",
    "pageTitle": "{{platform}} · {{market}}",
    "pageMeta": "共 {{count}} 条 · 更新于 {{updated}}",
    "applyEditsWithCount": "应用修改（{{n}} 条）",
    "copyFailed": "复制失败",
    "search": "搜 SKU 或标题",
    "searchBtn": "搜索",
    "previewCount": "显示 {{shown}} / {{total}}",
    "loading": "加载中…",
    "colTitle": "标题",
    "colColor": "颜色",
    "colSize": "尺码",
    "colAdTitle": "Feed 标题",
    "colAdColor": "Feed 颜色",
    "colAdSize": "Feed 尺码",
    "pickImage": "选 Feed 主图",
    "prev": "上一页",
    "next": "下一页",
    "applyEdits": "应用到当前 Feed",
    "applying": "应用中…",
    "applyOk": "已写回并更新 Feed",
    "saveRow": "保存",
    "savingRow": "保存中…",
    "deleteRow": "删除",
    "deletingRow": "删除中…",
    "rowSaved": "已保存本条",
    "rowDeleted": "已从 Feed 移除",
    "deleteRowConfirm": "从 Feed 中移除这条 SKU？不会删除 Shopify 商品。",
    "noEdits": "没有可应用的修改",
    "csvDownloaded": "CSV 已下载",
    "snapshots": "历史版本",
    "snapshotsHelp": "只读快照。恢复会覆盖当前稳定链接上的文件。",
    "noSnapshots": "还没有快照 — 下次更新后会出现。",
    "restore": "恢复为当前",
    "restored": "已恢复为当前 Feed",
    "markets": {
      "US": { "title": "美国 (英文) {{ccy}}", "subtitle": "United States (English)" },
      "DE": { "title": "德国 (德文) {{ccy}}", "subtitle": "Germany (German)" },
      "FR": { "title": "法国 (法文) {{ccy}}", "subtitle": "France (French)" },
      "ES": { "title": "西班牙 (西班牙文) {{ccy}}", "subtitle": "Spain (Spanish)" },
      "IT": { "title": "意大利 (意大利文) {{ccy}}", "subtitle": "Italy (Italian)" }
    }
  },
  "targets": {
    "platforms": "广告投到哪里",
    "markets": "目标市场",
    "marketsWithCcy": "目标市场（店币 {{ccy}}）",
    "marketsHelp": "默认美国（USD）。选了哪个市场，就请在 Shopify 把页面展示改成对应币种；不一致会拦截。"
  },
  "images": {
    "heading": "选一张给广告用的主图",
    "help": "只改广告 Feed 里的图，不会改你 Shopify 商品页。带「推荐」的一般更干净；标「不建议」的多半是批发站图。",
    "loading": "加载商品图片…",
    "empty": "未找到候选图片，请先在 Shopify 上传商品图。",
    "recommended": "推荐",
    "risky": "不建议",
    "save": "使用选中图并重生成 Feed",
    "saving": "保存中…",
    "cancel": "取消"
  },
  "products": {
    "heading": "本范围商品（已选 {{selected}}/{{total}}，{{variants}} 个规格）",
    "help": "先看图再勾选要进 Feed 的商品。",
    "colSelect": "生成",
    "vendor": "Shopify Vendor：{{vendor}}",
    "variantCount": "{{n}} 个规格",
    "hintColor": "缺颜色",
    "hintSize": "缺尺码",
    "hintImage": "建议换主图",
    "hintWording": "用词需改",
    "needsInListHint": "{{n}} 件货有待改项 — 已排在列表前面。",
    "fixThis": "改全部规格",
    "fixThisHint": "点「改全部规格」会勾选下面全部待改规格，再到上方一次填色/码。",
    "fixColorBtn": "改颜色",
    "fixSizeBtn": "改尺码",
    "fixWordingBtn": "去 Shopify 改用词",
    "search": "搜索产品名称、类型、品牌...",
    "selectAll": "全选",
    "deselectAll": "取消全选",
    "colProduct": "产品",
    "colType": "类型",
    "colVariants": "规格数",
    "colInventory": "库存",
    "colStatus": "状态",
    "colAdImage": "广告主图",
    "colActions": "操作",
    "editInShopify": "在 Shopify 编辑这件",
    "noStock": "无库存",
    "active": "在售",
    "changeAdImage": "换广告图",
    "afterGenerate": "生成后再选",
    "selectA11y": "选择 {{title}}",
    "loading": "正在加载产品..."
  },
  "tags": {
    "colorMulti": "颜色：Multicolor（智能兜底）",
    "sizeOne": "尺码：One Size（智能兜底）",
    "colorExtracted": "颜色：{{value}}（从文案提取）",
    "colorAi": "颜色：{{value}}（AI）",
    "colorDone": "颜色已提取",
    "sizeExtracted": "尺码：{{value}}（从文案提取）",
    "sizeDone": "尺码已补全",
    "noGtin": "无码通道（有真条码可到 Shopify 补）",
    "adult": "已标成人向（护号）"
  },
  "msg": {
    "bootIncomplete": "店铺连接未完成: {{detail}}",
    "bootFailed": "店铺连接失败: {{detail}}",
    "loadProductsFailed": "加载产品失败: {{detail}}",
    "needProduct": "请至少选择一个产品",
    "needPlatformMarket": "请至少选择一个平台和一个市场",
    "needBrand": "请先在下方「广告品牌」填写并点「确认品牌」。服饰类 Google 需要 brand，空品牌容易因 Missing brand 拒审。",
    "quotaShort": "配额不足：需要 {{need}}，剩余 {{left}}。请升级套餐。",
    "checking": "安检进行中，请稍候。我们会清洗标题、补齐颜色尺码，并开通无码通道。",
    "genFailed": "生成失败",
    "blockedOnly": "未能生成 Feed：{{countries}} 因币种不一致已拦截。请在 Shopify 改成与所选市场一致的展示币后再试。",
    "doneFatal": "安检完成：Feed 已生成，但有 {{fatals}} 条高风险仍写进文件。请先看下方清单，不要急着当「已过审」。",
    "doneWarn": "安检完成：已自动处理 {{auto}} 项，还有 {{warn}} 项建议你抽查后再交给 Google。",
    "doneOk": "安检完成：字段齐全，可以把 Feed 链接配进 Google Merchant Center。",
    "doneMergeOk": "已把这件商品加入当前 Feed（原有商品保留）。",
    "regenConfirm": "所选里有 {{n}} 件已经在 Feed 里。要重新生成并覆盖吗？（会再扣配额）",
    "mergeConfirm": "将把 {{n}} 件商品合并进当前 Feed（已有商品保留）。继续？",
    "alsoBlocked": " 另有 {{count}} 个市场因币种被拦截。",
    "noFeed": "未能生成 Feed：没有可写入的国家或产品。",
    "genFailedDetail": "生成失败: {{detail}}",
    "needSku": "请先勾选要修正的 SKU",
    "patchOk": "✅ 批量修正 {{updated}} 个变体{{missing}}，Feed 已刷新",
    "patchMissing": "，{{count}} 个 SKU 未找到",
    "patchFailed": "批量修正失败: {{detail}}",
    "imagesLoadFailed": "加载商品图片失败: {{detail}}",
    "needImage": "请选择一张主图",
    "imageSaved": "✅ {{sku}} 广告主图已更新，Feed 已刷新",
    "imageFailed": "主图更新失败: {{detail}}",
    "complianceDone": "网站合规：{{light}}（通过 {{pass}} · 建议 {{warn}} · 缺失 {{fail}}）",
    "complianceFailed": "网站合规诊断失败: {{detail}}",
    "brandEmpty": "请填写广告品牌后再确认。服饰类 Google 需要 brand。",
    "brandSaved": "广告品牌已保存为「{{brand}}」。生成 Feed 时会写入 g:brand。",
    "brandFailed": "保存广告品牌失败: {{detail}}",
    "lightGreen": "绿",
    "lightYellow": "黄",
    "lightRed": "红"
  },
  "rules": {
    "C01": {
      "msg": "服装类缺颜色，已自动填 Multicolor",
      "sug": "若商品有明确颜色，请在 Shopify 变体中设置 Color 后重新生成"
    },
    "C02": {
      "msg": "从文案提取颜色 → {{after}}",
      "sug": ""
    },
    "S01": {
      "msg": "服装/鞋服类缺尺码，已自动填 One Size",
      "sug": "若商品有真实尺码，请在 Shopify 变体中添加 Size 后重新生成"
    },
    "S05": {
      "msg": "尺码别名已归一为 One Size（原: {{before}}）",
      "sug": ""
    },
    "S02": {
      "msg": "已默认 age_group=adult",
      "sug": "若为童装请在店铺或后台改为 kids/toddler/infant"
    },
    "S03": {
      "msg": "已默认 condition=new",
      "sug": ""
    },
    "S04": {
      "msg": "已对齐 gender={{after}}",
      "sug": "可按类目/标题改为 female / male / unisex"
    },
    "ID01": {
      "msg": "无条码商品：已走无码通道 identifier_exists=no",
      "sug": "若有 UPC/EAN 请填写 gtin；否则保持无码并确保 brand 有效"
    },
    "ID02": {
      "msgReplaced": "品牌含 myshopify.com，已替换为店铺品牌 {{after}}",
      "msgWarn": "品牌含 myshopify.com（{{before}}），请配置有效店铺品牌",
      "sug": "设置 default_brand，勿使用 *.myshopify.com 作为品牌"
    },
    "M01": {
      "msg": "材质已译为英文 → {{after}}",
      "sug": "请确认与商品实物一致"
    },
    "M03": {
      "msg": "从标题/面料栏推断材质 → {{after}}",
      "sug": "建议在 Shopify 填写准确面料成分"
    },
    "M02": {
      "msg": "服装类缺少材质 material，GMC 可能提示属性不完整",
      "sug": "在 Shopify 商品/描述中补充面料（如 Cotton / Polyester）后重新生成"
    },
    "D01": {
      "msg": "原描述中文占比过高，已用英文摘要兜底",
      "sug": "补充英文详情可提升购物广告质量分"
    },
    "D02": {
      "msg": "描述已格式化并尽量英文化属性标签",
      "sug": ""
    },
    "D03": {
      "msg": "描述含大量中文，已替换为英文摘要（护 GMC 语种一致性）",
      "sug": "请在 Shopify 补充英文商品详情后重新生成"
    },
    "T01": {
      "msg": "标题为空",
      "sug": "填写有效商品标题后重新生成"
    },
    "I01": {
      "msg": "主图为空",
      "sug": "在 Shopify 上传主图后重新生成"
    },
    "I02": {
      "msg": "主图不是绝对 URL",
      "sug": "使用 https 图片链接"
    },
    "I03": {
      "msg": "主图疑似来自批发平台（{{detail}}）",
      "sug": "在下方「主图建议更换」从商品图库选一张干净主图"
    },
    "P02": {
      "msg": "价格无效或为 0",
      "sug": "在 Shopify 设置有效价格后重新生成"
    },
    "L01": {
      "msg": "商品链接无效",
      "sug": "检查店铺站点 URL 与商品 handle"
    },
    "V01": {
      "msg": "服装类建议提供颜色",
      "sug": "在 Shopify 变体中设置 Color"
    },
    "VA01": {
      "msgFallback": "变体缺颜色，已填 Multicolor",
      "msgClean": "颜色已清洗 → {{after}}",
      "sug": ""
    },
    "VA02": {
      "msgFallback": "服装缺尺码，已填 One Size",
      "msgClean": "尺码已清洗 → {{after}}",
      "sug": ""
    },
    "VA03": {
      "msg": "已补 size_system=US, size_type=Regular",
      "sug": ""
    },
    "VA04": {
      "msg": "缺少 Shopify Variant ID，链接无法定位到具体色/码；请重新同步后再投放",
      "sug": "在 Shopify 重新同步该商品，确认变体存在后再生成 Feed"
    },
    "IMG01": {
      "msg": "已去除水印并替换主图",
      "sug": ""
    },
    "IMG02": {
      "msgEmpty": "主图为空，无法去水印",
      "msgFail": "主图疑似含水印，处理失败，请替换",
      "sugEmpty": "上传至少一张商品图片",
      "sugFail": "手动替换为干净实拍图"
    },
    "AD01": {
      "msg": "已为敏感类目注入 adult=yes（主动合规，护号优先）",
      "sug": "广告将仅成人向展示，保护账号免误判"
    },
    "SEN": {
      "soft": "敏感词已软化（{{id}}）",
      "flag": "检测到成人向信号（{{id}}）",
      "block": "敏感高风险（{{id}}）：建议勿投放 GMC，先人工审核",
      "sug": "请按提示同步改 Shopify 文案；FATAL 建议勿投放"
    }
  },
  "complianceChecks": {
    "POL_SCAN": {
      "unknown": "无法通过 App 读取 Shopify 政策（缺少 read_legal_policies 权限），请在后台 Settings → Policies 手动确认。"
    },
    "policyLabel": {
      "POL_REFUND": "退换货政策",
      "POL_PRIVACY": "隐私政策",
      "POL_SHIPPING": "运费政策",
      "POL_TERMS": "服务条款"
    },
    "policyMissing": "缺少{{label}}",
    "policyMissingSug": "在 Shopify Settings → Policies 填写并发布",
    "policyPresent": "{{label}}已配置",
    "policyPresentSug": "确保页脚菜单链到该政策页",
    "policyWeak": "{{label}}内容可能过短或像占位文案",
    "SITE_HTTPS": {
      "pass": "店铺 URL 使用 HTTPS",
      "fail": "店铺 URL 未使用 HTTPS",
      "failSug": "在 Shopify 使用自定义域名并启用 SSL"
    },
    "SITE_REACHABLE": {
      "pass": "首页可访问",
      "http": "首页返回 HTTP {{code}}",
      "httpSug": "确认店铺未密码保护且域名可公开访问",
      "down": "无法探测首页（超时或网络错误）",
      "downSug": "手动在浏览器打开店铺确认"
    },
    "FOOT": {
      "pass": "{{label}}已在页脚链出",
      "warn": "{{label}}在页面有链接，但未在 <footer> 内发现",
      "warnSug": "Online Store → Navigation → Footer menu 添加政策链接",
      "fail": "{{label}}已配置，但首页/页脚未见链接",
      "failSug": "将政策页加入 Footer menu（GMC 要求可发现）"
    },
    "FOOT_CONTACT": {
      "pass": "Contact 已在页脚链出",
      "warn": "Contact 在页面有链接，但未在 <footer> 内发现",
      "warnSug": "将 Contact 页加入 Footer menu"
    },
    "FOOT_SCAN": {
      "warn": "无法解析首页 HTML，跳过页脚链接检查"
    },
    "CONTACT_PAGE": {
      "pass": "找到联系方式页",
      "warn": "未找到 /pages/contact，但店铺后台有邮箱/电话",
      "warnSug": "建议创建 Contact 页并在页脚链接（GMC 常查前台可见联系方式）",
      "fail": "未找到 Contact 页且缺少可见联系方式",
      "failSug": "添加 Contact 页：邮箱 + 电话或地址，并放入页脚菜单"
    },
    "CURR": {
      "pass": "{{country}} 市场：店币与 Feed 目标一致或可投放",
      "warn": "{{country}} 需要匹配的展示币种 — 请先在 Shopify Markets 对齐再生成",
      "warnSug": "在 Shopify Markets / 展示币种改为与目标市场一致后再生成 Feed"
    }
  }
},
};
