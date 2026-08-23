"""Public legal pages for Shopify App Store listing URLs."""

from __future__ import annotations

import os

SUPPORT_EMAIL = os.getenv("ADFEED_SUPPORT_EMAIL", "support@deltfu.com")


def privacy_html() -> str:
    email = SUPPORT_EMAIL
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>AdFeed AI Privacy Policy</title>
</head>
<body>
  <h1>AdFeed AI Privacy Policy</h1>
  <p>Last updated: 18 August 2026</p>
  <p>AdFeed AI (“we”) provides a Shopify app that generates shopping ad feeds from a merchant’s catalog.</p>
  <h2>Information we collect through Shopify</h2>
  <ul>
    <li>Shop domain, shop name, and Admin API access token</li>
    <li>Product catalog snapshots (titles, variants, images, prices as shown in Admin)</li>
    <li>Ad brand the merchant confirms in the app</li>
    <li>Generated feed files and quality reports</li>
    <li>App subscription / quota records via Shopify Billing</li>
  </ul>
  <h2>Information we do not collect</h2>
  <p>We do not collect customer personal information, order data, or payment card details. We do not drop tracking cookies on storefront buyers.</p>
  <h2>How we use data</h2>
  <p>We use shop and product data only to generate and host feed files and to show in-app quality hints. We do not sell merchant data.</p>
  <h2>Retention and deletion</h2>
  <p>While the app is installed we keep catalog snapshots needed to serve feeds. After uninstall, Shopify sends a <code>shop/redact</code> request (typically 48 hours later). We then delete that shop’s products, jobs, feed files, and store record. Customer redaction webhooks are acknowledged; we store no customer PII to erase.</p>
  <h2>Merchant Center</h2>
  <p>AdFeed AI does not guarantee Google Merchant Center or ads approval. Feeds still require merchant review.</p>
  <h2>Contact</h2>
  <p>Privacy questions: <a href="mailto:{email}">{email}</a></p>
</body>
</html>
"""


def support_html() -> str:
    email = SUPPORT_EMAIL
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>AdFeed AI Support</title>
</head>
<body>
  <h1>AdFeed AI Support</h1>
  <p>Email <a href="mailto:{email}">{email}</a>. We aim to reply within two business days.</p>
  <p>In the app: generate a feed, copy the URL into Google Merchant Center, and use “Edit this in Shopify” or in-app color/size fill for missing attributes.</p>
  <p>AdFeed AI does not guarantee Merchant Center approval.</p>
</body>
</html>
"""
