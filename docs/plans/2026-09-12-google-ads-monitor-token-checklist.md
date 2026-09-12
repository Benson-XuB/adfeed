# Google Ads API — what to do after this ship

The marketing tool is live in **demo mode** without a developer token.

## Cloud Console

1. OAuth Web client (can reuse existing client id/secret)
2. Add authorized redirect URI:
   `https://deltfu.com/api/public/google-ads/oauth/callback`
3. Enable **Google Ads API** on the GCP project

## Ads API Center

1. Apply for a **Developer Token** (Basic access is enough to start)
2. When approved, put on the server `/opt/adfeed/phase0/.env`:

```bash
GOOGLE_ADS_OAUTH_REDIRECT_URI=https://deltfu.com/api/public/google-ads/oauth/callback
GOOGLE_ADS_DEVELOPER_TOKEN=...your token...
# optional if using MCC:
# GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890
```

3. Ensure `GOOGLE_OAUTH_CLIENT_ID` / `SECRET` are already present (same as MC tool is fine)
4. `sudo systemctl restart adfeed-api`

## Verify

- `/api/public/google-ads/status` → `ads_api_configured: true`
- Connect on `/tools/google-ads-monitor` → pick customer → Load live report

## Does not touch

Shopify App, App Store review build, MC `/api/public/google/*` cookie.
