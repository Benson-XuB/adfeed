/** Developed-market feed targets — keep in sync with `adfeed/market_pricing.py`. */
export const TARGET_MARKETS = [
  { code: "US", currency: "USD" },
  { code: "CA", currency: "CAD" },
  { code: "GB", currency: "GBP" },
  { code: "DE", currency: "EUR" },
  { code: "FR", currency: "EUR" },
  { code: "ES", currency: "EUR" },
  { code: "IT", currency: "EUR" },
  { code: "NL", currency: "EUR" },
  { code: "BE", currency: "EUR" },
  { code: "AT", currency: "EUR" },
  { code: "IE", currency: "EUR" },
  { code: "PT", currency: "EUR" },
  { code: "FI", currency: "EUR" },
  { code: "SE", currency: "SEK" },
  { code: "NO", currency: "NOK" },
  { code: "DK", currency: "DKK" },
  { code: "CH", currency: "CHF" },
  { code: "PL", currency: "PLN" },
  { code: "AU", currency: "AUD" },
  { code: "NZ", currency: "NZD" },
  { code: "JP", currency: "JPY" },
  { code: "KR", currency: "KRW" },
  { code: "SG", currency: "SGD" },
  { code: "HK", currency: "HKD" },
  { code: "TW", currency: "TWD" },
  { code: "QA", currency: "QAR" },
  { code: "AE", currency: "AED" },
] as const;

export type TargetMarket = (typeof TARGET_MARKETS)[number];
export type TargetMarketCode = TargetMarket["code"];
