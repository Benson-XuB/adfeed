"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useEffect } from "react";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-stone-800 border-t-transparent animate-spin" />
      </div>
    );
  }

  const navItems = [
    { href: "/dashboard", label: "Overview", icon: "□" },
    { href: "/shopify", label: "Shopify", icon: "⬡" },
    { href: "/upload", label: "Upload", icon: "↑" },
    { href: "/feeds", label: "Feeds", icon: "⇣" },
  ];

  if (user?.plan === "free") {
    navItems.push({ href: "/upgrade", label: "Upgrade", icon: "✦" });
  }

  return (
    <div className="flex-1 flex">
      {/* Sidebar */}
      <aside className="w-56 border-r border-stone-200 bg-white flex flex-col shrink-0">
        <div className="px-5 py-5 border-b border-stone-100">
          <Link href="/dashboard" className="text-lg font-bold tracking-tight">
            AdFeed AI
          </Link>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ href, label, icon }) => {
            const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-3 px-3 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "bg-stone-900 text-white"
                    : "text-stone-600 hover:bg-stone-100 hover:text-stone-900"
                }`}
              >
                <span className="text-lg leading-none">{icon}</span>
                {label}
              </Link>
            );
          })}
        </nav>

        {/* User / quota */}
        <div className="px-5 py-4 border-t border-stone-100 space-y-3">
          <div className="flex items-center gap-2">
            {user.avatar_url ? (
              <img src={user.avatar_url} alt="" className="w-6 h-6 rounded-full" />
            ) : (
              <div className="w-6 h-6 rounded-full bg-stone-200 flex items-center justify-center text-xs font-bold text-stone-500">
                {user.email[0].toUpperCase()}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium truncate">{user.name || user.email}</div>
              <div className="text-[10px] text-stone-400 uppercase tracking-wider">{user.plan}</div>
            </div>
          </div>
          <div className="text-[10px] text-stone-400">
            Quota: {user.quota_used}/{user.quota_total} SKUs
          </div>
          <div className="progress-bar">
            <div
              className="progress-bar-fill"
              style={{ width: `${user.quota_total > 0 ? (user.quota_used / user.quota_total) * 100 : 0}%` }}
            />
          </div>
          <button
            onClick={() => { logout(); router.push("/"); }}
            className="text-xs text-stone-400 hover:text-stone-700 transition-colors"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 bg-stone-50 overflow-auto">
        <div className="max-w-5xl mx-auto px-8 py-8">{children}</div>
      </main>
    </div>
  );
}
