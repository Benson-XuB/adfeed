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
     * Explain how AdFeed AI generates Google, Meta, and TikTok shopping feeds from the Shopify catalog, including missing color/size fixes. Does not guarantee Merchant Center approval.
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
