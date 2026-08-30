export default () => {
  shopify.tools.register("describe_adfeed", async () => {
    return {
      summary:
        "AdFeed AI builds a Google Shopping data feed for stores that import products from 1688. Open the app home: confirm your ad brand (not the 1688 supplier name), select products, generate, then copy the feed URL into Google Merchant Center. Optional color/size tips appear when variants have Color/Size options; generation is not blocked when they are missing. The app does not invent barcodes and does not guarantee Merchant Center approval.",
    };
  });
};
