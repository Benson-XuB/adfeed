import '@shopify/ui-extensions';

//@ts-ignore
declare module './src/index.js' {
  interface DescribeAdfeedInput {
    [k: string]: unknown;
  }

  interface DescribeAdfeedOutput {
    /**
     * What the app does for the merchant
     */
    summary: string;
    [k: string]: unknown;
  }

  interface ShopifyTools {
    /**
     * Explain how AdFeed AI optimizes 1688-imported catalog products into a Google Shopping data feed: ad brand, generate, feed URL, optional color/size tips. Google only. Does not guarantee Merchant Center approval.
     */
    register(
      name: 'describe_adfeed',
      handler: (
        input: DescribeAdfeedInput,
      ) => DescribeAdfeedOutput | Promise<DescribeAdfeedOutput>,
    ): () => void;
  }

  const shopify: import('@shopify/ui-extensions/admin').WithGeneratedTools<
    import('@shopify/ui-extensions/admin.app.tools.data').Api,
    ShopifyTools
  >;
  const globalThis: { shopify: typeof shopify };
}
