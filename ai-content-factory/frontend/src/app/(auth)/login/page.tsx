"use client";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Factory, Loader2 } from "lucide-react";
import { authApi } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(false);

  // Handle OAuth callback (code param)
  const code = searchParams.get("code");

  useEffect(() => {
    if (code) {
      // This is handled by the /auth/google/callback backend route
      // Frontend just reads the token from query param if redirected here
    }
    // Check if already logged in
    const token = localStorage.getItem("access_token");
    if (token) router.push("/dashboard");
  }, []);

  const handleGoogleLogin = async () => {
    setLoading(true);
    try {
      const res = await authApi.getLoginUrl();
      window.location.href = res.data.auth_url;
    } catch {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="glass-card p-10 w-full max-w-sm text-center">
        <div className="w-14 h-14 rounded-2xl bg-primary/20 flex items-center justify-center mx-auto mb-5">
          <Factory className="w-7 h-7 text-primary" />
        </div>
        <h1 className="text-2xl font-display font-bold text-foreground mb-2">
          AI Content Factory
        </h1>
        <p className="text-sm text-foreground-muted mb-8">
          Automated video → clips pipeline
        </p>
        <button
          onClick={handleGoogleLogin}
          disabled={loading}
          className="w-full flex items-center justify-center gap-3 px-5 py-3 bg-white text-gray-800 font-medium rounded-xl hover:bg-gray-100 transition-colors disabled:opacity-60"
        >
          {loading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
          )}
          Sign in with Google
        </button>
      </div>
    </div>
  );
}
