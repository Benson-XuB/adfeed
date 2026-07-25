"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { getGoogleUrl, requestMagicLink, verifyMagicLink } from "@/lib/api";

export default function LoginPage() {
  const { setAuth } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [magicToken, setMagicToken] = useState("");
  const [error, setError] = useState("");

  const handleGoogle = async () => {
    const url = await getGoogleUrl();
    window.location.href = url;
  };

  const handleMagicLink = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await requestMagicLink(email);
      setSent(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to send link");
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const { token, user } = await verifyMagicLink(magicToken);
      setAuth(token, user);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Invalid link");
    }
  };

  return (
    <main className="flex-1 flex items-center justify-center px-6 py-20">
      <div className="w-full max-w-md">
        <h1 className="text-3xl font-black tracking-tight mb-2">Sign in</h1>
        <p className="text-stone-500 mb-8 text-sm">
          One click with Google, or a magic link to your inbox.
        </p>

        {/* Google */}
        <button onClick={handleGoogle} className="btn w-full mb-6 justify-center text-base py-3">
          <svg className="w-5 h-5" viewBox="0 0 24 24">
            <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
            <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
            <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
          </svg>
          Continue with Google
        </button>

        <div className="flex items-center gap-3 mb-6">
          <hr className="flex-1 border-stone-200" />
          <span className="text-xs text-stone-400 tracking-widest">OR</span>
          <hr className="flex-1 border-stone-200" />
        </div>

        {/* Magic Link */}
        {!sent ? (
          <form onSubmit={handleMagicLink}>
            <input
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input mb-3"
              required
            />
            <button type="submit" className="btn btn-outline w-full justify-center text-base py-3">
              Send magic link
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerify}>
            <p className="text-sm text-stone-500 mb-3">
              We sent a link to <strong>{email}</strong>. Paste the token from the link below.
            </p>
            <input
              type="text"
              placeholder="Paste token from link"
              value={magicToken}
              onChange={(e) => setMagicToken(e.target.value)}
              className="input mb-3"
              required
            />
            <button type="submit" className="btn w-full justify-center text-base py-3">
              Verify & sign in
            </button>
          </form>
        )}

        {error && (
          <div className="mt-4 p-3 border border-red-200 bg-red-50 text-red-700 text-sm">{error}</div>
        )}
      </div>
    </main>
  );
}
