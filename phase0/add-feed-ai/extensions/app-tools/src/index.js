export default () => {
  shopify.tools.register("describe_adfeed", async () => {
    return {
      summary:
        "AdFeed AI generates Google Shopping feeds from this store’s catalog. Open the app home: confirm ad brand, select products, generate, then copy the feed URL into Merchant Center. Missing color/size can be filled in the app or by editing the variant in Shopify. The app does not invent barcodes and does not guarantee Merchant Center approval.",
    };
  });
};
