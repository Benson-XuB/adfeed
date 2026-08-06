# E2E checklist — App multi-platform generate

Manual + automated smoke for Tasks 1–11.

## Manual (dev store)

1. Install app on a Shopify development store
2. Subscribe to Starter (test charge) via App billing CTA
3. Select **3 products**, platforms **Google + Meta**, markets **US + DE**
4. Confirm live estimate shows **12**
5. Generate → expect **4 durable feed URLs** (`google/us`, `google/de`, `meta/us`, `meta/de`)
6. Confirm quota used **+= 12**
7. Call `POST /api/app/generate` without `Authorization` → **401**
8. Generate with watermark toggle **off** → image pipeline not invoked

## Automated smoke

```bash
cd phase0
python -m pytest tests/test_store_schema.py tests/test_shopify_session.py \
  tests/test_shopify_billing.py tests/test_quota.py \
  tests/test_layered_optimize.py tests/test_e2e_smoke.py -v
```

## URL shape

`https://deltfu.com/feeds/{store_id}/{platform}/{lang}.xml`  
TikTok: `.../{lang}.csv`
