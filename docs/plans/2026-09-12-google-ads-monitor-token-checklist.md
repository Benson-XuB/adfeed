# Google Ads API — after developer-token sunset (2026-09-09)

Access levels live on the **Google Cloud project** (Test / Explorer / Basic).
Developer tokens are optional/ignored for Ads API access management.

## Cloud Console (`adfeed-ai-dev`)

1. Enable **Google Ads API**
2. Overview → apply for **Explorer** when you need production accounts (Test is enough for test accounts)
3. OAuth Web client redirect URI:
   `https://deltfu.com/api/public/google-ads/oauth/callback`
4. Reuse `GOOGLE_OAUTH_CLIENT_ID` / `SECRET` (same as MC tool is fine)

## Server `.env`

```bash
GOOGLE_ADS_OAUTH_REDIRECT_URI=https://deltfu.com/api/public/google-ads/oauth/callback
# optional leftover; not required for live mode anymore:
# GOOGLE_ADS_DEVELOPER_TOKEN=
# GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890
```

`sudo systemctl restart adfeed-api` after env changes.

## Test with a Test Ads account (while Cloud access = Test)

1. Create a Google Ads **test manager** + test client account
2. Open https://deltfu.com/tools/google-ads-monitor
3. **Connect Google Ads** (sign in with the test account Google user)
4. Pick customer → **Load live report**

## Verify

- `/api/public/google-ads/status` → `ads_api_configured: true`, `mode: live`
- Demo still works via **Show sample** / `force_demo=1`

## Does not touch

Shopify App, App Store review build, MC `/api/public/google/*` cookie.
