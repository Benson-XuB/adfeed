import { useEffect } from "react";
import type { HeadersFunction, LoaderFunctionArgs } from "react-router";
import { Outlet, useLoaderData, useRouteError } from "react-router";
import { boundary } from "@shopify/shopify-app-react-router/server";
import { AppProvider } from "@shopify/shopify-app-react-router/react";

import { authenticate } from "../shopify.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  await authenticate.admin(request);

  const backendUrl = (
    process.env.BACKEND_URL ||
    process.env.VITE_BACKEND_URL ||
    ""
  ).replace(/\/$/, "");

  // eslint-disable-next-line no-undef
  return {
    apiKey: process.env.SHOPIFY_API_KEY || "",
    backendUrl,
  };
};

export default function App() {
  const { apiKey, backendUrl } = useLoaderData<typeof loader>();

  useEffect(() => {
    if (backendUrl) {
      window.__ADFEED_BACKEND_URL__ = backendUrl;
    }
  }, [backendUrl]);

  if (typeof window !== "undefined" && backendUrl) {
    window.__ADFEED_BACKEND_URL__ = backendUrl;
  }

  return (
    <AppProvider embedded apiKey={apiKey}>
      <s-app-nav>
        <s-link href="/app">Home</s-link>
        <s-link href="/app/plans">Plans</s-link>
      </s-app-nav>
      <Outlet />
    </AppProvider>
  );
}

export function ErrorBoundary() {
  return boundary.error(useRouteError());
}

export const headers: HeadersFunction = (headersArgs) => {
  return boundary.headers(headersArgs);
};
