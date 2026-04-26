"use client";
import { useEffect, useRef, Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, XCircle } from "lucide-react";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const called = useRef(false);

  useEffect(() => {
    if (called.current) return;
    called.current = true;

    // Case 1: Direct token in URL (future)
    const directToken = searchParams.get("access_token");
    if (directToken) {
      localStorage.setItem("access_token", directToken);
      router.replace("/dashboard");
      return;
    }

    // Case 2: Google OAuth code — forward to backend
    const code = searchParams.get("code");
    const state = searchParams.get("state");

    if (!code) {
      const errorParam = searchParams.get("error");
      setError(errorParam ?? "No authorization code received from Google");
      setTimeout(() => router.replace("/login"), 3000);
      return;
    }

    const params = new URLSearchParams({ code, ...(state ? { state } : {}) });

    fetch(`${BASE_URL}/api/v1/auth/google/callback?${params.toString()}`)
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail ?? `Authentication failed (${res.status})`);
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
      <div
        style={{
          minHeight: "100vh",
          background: "#080810",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "16px",
          fontFamily: "Inter, sans-serif",
        }}
      >
        <XCircle style={{ width: 40, height: 40, color: "#FF6B6B" }} />
        <p style={{ color: "#E8E8F0", fontWeight: 600, margin: 0 }}>Login gagal</p>
        <p style={{ color: "#6B6B8A", fontSize: 14, margin: 0 }}>{error}</p>
        <p style={{ color: "#6B6B8A", fontSize: 12, margin: 0 }}>
          Mengalihkan ke halaman login…
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#080810",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "16px",
        fontFamily: "Inter, sans-serif",
      }}
    >
      <Loader2
        style={{ width: 32, height: 32, color: "#6C63FF", animation: "spin 1s linear infinite" }}
      />
      <p style={{ color: "#6B6B8A", fontSize: 14, margin: 0 }}>Memproses login…</p>
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: "100vh", background: "#080810" }} />}>
      <CallbackContent />
    </Suspense>
  );
}
