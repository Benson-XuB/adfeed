"use client";

import { useAuth } from "@/lib/auth";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function LandingPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (!loading && user) router.push("/dashboard");
  }, [user, loading, router]);

  if (loading || (mounted && user)) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-stone-800 border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <main className="flex-1">
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-5 border-b border-stone-200 bg-white/80 backdrop-blur sticky top-0 z-50">
        <span className="text-lg font-bold tracking-tight">AdFeed AI</span>
        <div className="flex items-center gap-4">
          <Link href="/login" className="text-sm font-medium text-stone-500 hover:text-stone-900 transition-colors">
            Sign in
          </Link>
          <Link href="/login" className="btn btn-sm">
            Start free
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-6 pt-28 pb-20 text-center">
        <div className="animate-slide-up">
          <span className="tag mb-6 inline-block">BETA · Google Shopping Compliance</span>
          <h1 className="text-5xl md:text-7xl font-black tracking-tight leading-[1.05] mb-6">
            Your 1688 data,
            <br />
            <span className="text-stone-400">Google-ready</span>{" "}
            in seconds.
          </h1>
          <p className="text-lg md:text-xl text-stone-500 max-w-2xl mx-auto mb-10 leading-relaxed">
            Upload any Chinese supplier spreadsheet. Get AI-optimized titles,
            local cultural keywords, GMC-compliant feeds — across 5 countries.
            Zero manual editing.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link href="/login" className="btn text-base px-8 py-3">
              Start free — 10 SKUs
            </Link>
            <Link href="#how" className="btn btn-outline text-base px-8 py-3">
              How it works
            </Link>
          </div>
        </div>

        {/* Stats bar */}
        <div className="grid grid-cols-3 gap-8 mt-20 pt-12 border-t border-stone-200 animate-slide-up delay-100">
          {[
            ["5", "Countries"],
            ["12", "Product Categories"],
            ["96%", "AI Accuracy"],
          ].map(([num, label]) => (
            <div key={label}>
              <div className="text-3xl md:text-5xl font-black tracking-tight">{num}</div>
              <div className="text-xs text-stone-400 tracking-widest uppercase mt-1">{label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="bg-stone-50 border-y border-stone-200 py-24">
        <div className="max-w-5xl mx-auto px-6">
          <h2 className="text-3xl font-black tracking-tight mb-16 text-center">How it works</h2>
          <div className="grid md:grid-cols-3 gap-8">
            {[
              { step: "01", title: "Upload", desc: "Drop any Excel, CSV, or text file — from 1688, Shopify, ERP, or a WeChat message." },
              { step: "02", title: "AI Cleans", desc: "Titles optimized for local search intent. Banned words removed. GPC categories matched. Cultural keywords injected." },
              { step: "03", title: "Export", desc: "Download a GMC-compliant RSS 2.0 feed. Inventory auto-updates. Out-of-stock auto-flagged." },
            ].map(({ step, title, desc }) => (
              <div key={step} className="card animate-slide-up" style={{ animationDelay: `${parseInt(step) * 0.1}s` }}>
                <div className="text-xs text-stone-400 tracking-widest mb-4">{step}</div>
                <h3 className="text-lg font-bold mb-2">{title}</h3>
                <p className="text-sm text-stone-500 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Feature grid */}
      <section className="max-w-5xl mx-auto px-6 py-24">
        <h2 className="text-3xl font-black tracking-tight mb-16 text-center">
          Built for dropshippers,<br />by someone who gets it.
        </h2>
        <div className="grid md:grid-cols-2 gap-6">
          {[
            { title: "No more GMC suspensions", desc: "Hardcoded banned-word firewall strips 'Best', 'No.1', and country-specific violations before they reach Google." },
            { title: "5 countries, native fluency", desc: "US, DE, FR, ES, IT — each with localized cultural keywords, seasonal awareness, and native-language tags." },
            { title: "Zero-token price updates", desc: "Product already in memory? Only price and inventory update — AI is not called. Your quota lasts." },
            { title: "Google Shopping ready XML", desc: "Dynamic RSS 2.0 feed at /user/google-feed.xml. JSON-LD structured data for AI search engines." },
            { title: "Any Excel format works", desc: "No column-name guessing. We detect title, material, color, price statistically — 8 formats tested." },
            { title: "Long-tail keyword engine", desc: "Category-specific title formulas with scene keywords (e.g., 'for Summer Wedding Guest') in the mobile-visible 70 chars." },
          ].map((f) => (
            <div key={f.title} className="card">
              <h3 className="font-bold mb-1">{f.title}</h3>
              <p className="text-sm text-stone-500 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="bg-stone-900 text-stone-50 py-24">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-3xl md:text-5xl font-black tracking-tight mb-4">
            Stop getting suspended.
          </h2>
          <p className="text-stone-400 mb-10 text-lg">
            Your first 10 SKUs are free. No credit card.
          </p>
          <Link href="/login" className="inline-flex items-center gap-2 px-8 py-3 text-base font-bold bg-white text-stone-900 hover:bg-stone-200 transition-colors">
            Start free →
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 text-center text-xs text-stone-400 border-t border-stone-200">
        &copy; {new Date().getFullYear()} AdFeed AI. Made for dropshippers who want to sleep better.
      </footer>
    </main>
  );
}
