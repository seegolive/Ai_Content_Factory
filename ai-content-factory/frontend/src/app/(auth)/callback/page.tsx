"use client";
import { useEffect, useRef, Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, CheckCircle, XCircle } from "lucide-react";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const called = useRef(false);

  useEffect(() => {
    if (called.current) return;
    called.current = true;

    // Case 1: Backend already gave us a token in the URL (future use)
    const directToken = searchParams.get("access_token");
    if (directToken) {
      localStorage.setItem("access_token", directToken);
      router.replace("/dashboard");
      return;
    }

    // Case 2: Google redirected here with code + state — forward to backend
    const code = searchParams.get("code");
    const state = searchParams.get("state");

    if (!code) {
      const errorParam = searchParams.get("error");
      setError(errorParam ?? "No authorization code received");
      setTimeout(() => router.replace("/login"), 3000);
      return;
    }

    const params = new URLSearchParams({ code, ...(state ? { state } : {}) });

    fetch(`${BASE_URL}/api/v1/auth/google/callback?${params.toString()}`)
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail ?? `Auth failed (${res.status})`);
        }
        return res.json();
      })
      .then((data: { access_token: string }) => {
        localStorage.setItem("access_token", data.access_token);
        router.replace("/dashboard");
      })
      .catch((err: Error) => {
        setError(err.message);
        setTimeout(() => router.replace("/login"), 3000);
      });
  }, []);

  if (error) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center gap-4">
        <XCircle className="w-10 h-10 text-accent" />
        <p className="text-foreground font-medium">Login gagal</p>
        <p className="text-sm text-foreground-muted">{error}</p>
        <p className="text-xs text-foreground-muted">Mengalihkan ke halaman login…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center gap-4">
      <Loader2 className="w-8 h-8 text-primary animate-spin" />
      <p className="text-sm text-foreground-muted">Memproses login…</p>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <CallbackContent />
    </Suspense>
  );
}
