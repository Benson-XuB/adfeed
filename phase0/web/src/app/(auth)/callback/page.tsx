"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { googleCallback } from "@/lib/api";

function CallbackInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { setAuth } = useAuth();
  const [error, setError] = useState("");
  const called = useRef(false);

  useEffect(() => {
    if (called.current) return;
    called.current = true;
    const code = params.get("code");
    if (!code) {
      setError("No authorization code received.");
      return;
    }
    googleCallback(code)
      .then(({ token, user }) => {
        setAuth(token, user);
        router.push("/dashboard");
      })
      .catch((err) => setError(err.message));
  }, [params, router, setAuth]);

  if (error) {
    return (
      <div className="text-center">
        <p className="text-red-600 mb-4">{error}</p>
        <a href="/login" className="btn btn-sm">Back to login</a>
      </div>
    );
  }

  return (
    <div className="text-center">
      <div className="w-6 h-6 border-2 border-stone-800 border-t-transparent animate-spin mx-auto mb-4" />
      <p className="text-stone-500 text-sm">Signing you in...</p>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <main className="flex-1 flex items-center justify-center">
      <Suspense fallback={
        <div className="text-center">
          <div className="w-6 h-6 border-2 border-stone-800 border-t-transparent animate-spin mx-auto mb-4" />
          <p className="text-stone-500 text-sm">Loading...</p>
        </div>
      }>
        <CallbackInner />
      </Suspense>
    </main>
  );
}
