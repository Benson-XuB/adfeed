"use client";

import Link from "next/link";

const SHOPIFY_APP_URL =
  process.env.NEXT_PUBLIC_SHOPIFY_APP_URL ||
  "https://apps.shopify.com/";

export default function LandingPage() {
  return (
    <main className="flex-1">
      <nav className="flex items-center justify-between px-8 py-5 border-b border-stone-200 bg-white/80 backdrop-blur sticky top-0 z-50">
        <span className="text-lg font-bold tracking-tight">AdFeed AI</span>
        <a
          href={SHOPIFY_APP_URL}
          className="btn btn-sm"
          target="_blank"
          rel="noreferrer"
        >
          Install Shopify App
        </a>
      </nav>

      <section className="max-w-5xl mx-auto px-6 pt-28 pb-20 text-center">
        <span className="tag mb-6 inline-block">Shopify App · Multi-platform feeds</span>
        <h1 className="text-5xl md:text-7xl font-black tracking-tight leading-[1.05] mb-6">
          AdFeed AI
        </h1>
        <p className="text-lg md:text-xl text-stone-500 max-w-2xl mx-auto mb-10 leading-relaxed">
          Install the Shopify App, select products, choose Google / Meta / TikTok
          and markets, then get durable feed URLs. CSV upload and Web SaaS login
          are retired — the App is the product.
        </p>
        <div className="flex items-center justify-center gap-4">
          <a
            href={SHOPIFY_APP_URL}
            className="btn text-base px-8 py-3"
            target="_blank"
            rel="noreferrer"
          >
            Install on Shopify
          </a>
          <Link href="/login" className="btn btn-outline text-base px-8 py-3 opacity-60">
            Legacy login (disabled)
          </Link>
        </div>
      </section>
    </main>
  );
}
