# App Home Extension

App home extensions render the app landing experience inside the Shopify Admin (`admin.app.home.render`).

## Localization

UI language follows the **Shopify admin locale** (not feed target markets US/DE/…):

| Admin language | UI |
|----------------|-----|
| starts with `zh` | Simplified Chinese (`zh-CN`) |
| everything else | English (`en`, default) |

- `locales/en.default.json` / `locales/zh-CN.json` — Shopify + catalog
- `src/i18n.js` — `t(key, vars)`
- `src/i18n-messages.js` — runtime fallback catalogs
- `src/event-i18n.js` — maps quality `rule_id` / store-compliance check `id` to UI language (so English admin does not show Chinese API messages)

When adding merchant-facing copy, update **both** locale JSON files and sync `i18n-messages.js`. New quality rules need `rules.<ID>.msg` / `.sug` entries.
## Key files

- `src/AppHome.jsx` — entry + routing
- `src/pages/HomePage.jsx` — feed check / generate UI
- `shopify.extension.toml` — extension config

Preview with `shopify app dev`.
