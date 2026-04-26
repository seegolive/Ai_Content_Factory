"use client";
import { Suspense, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { authApi } from "@/lib/api";

const PIPELINE_STEPS = [
  { label: "Upload", icon: "⬆" },
  { label: "Transcribe", icon: "🎙" },
  { label: "AI Score", icon: "✦" },
  { label: "Cut Clips", icon: "✂" },
  { label: "Publish", icon: "🚀" },
];

function LoginContent() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) router.replace("/dashboard");
  }, []);

  // Animate pipeline steps
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % PIPELINE_STEPS.length);
    }, 1200);
    return () => clearInterval(interval);
  }, []);

  const handleGoogleLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await authApi.getLoginUrl();
      window.location.href = res.data.auth_url;
    } catch {
      setError("Gagal memuat URL login. Coba lagi.");
      setLoading(false);
    }
  };

  return (
    <div className="login-root">
      {/* Animated background */}
      <div className="login-bg">
        <div className="login-orb login-orb-1" />
        <div className="login-orb login-orb-2" />
        <div className="login-orb login-orb-3" />
        <div className="login-grid" />
      </div>

      {/* Main card */}
      <div className="login-card">
        {/* Header */}
        <div className="login-logo">
          <div className="login-logo-icon">
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
              <rect x="2" y="8" width="6" height="12" rx="1.5" fill="#6C63FF" />
              <rect x="11" y="4" width="6" height="20" rx="1.5" fill="#00D4AA" />
              <rect x="20" y="10" width="6" height="8" rx="1.5" fill="#6C63FF" opacity="0.7" />
            </svg>
          </div>
          <div>
            <h1 className="login-title">AI Content Factory</h1>
            <p className="login-subtitle">Video → Viral Clips, otomatis</p>
          </div>
        </div>

        {/* Pipeline visualizer */}
        <div className="login-pipeline">
          {PIPELINE_STEPS.map((step, i) => (
            <div key={step.label} className="login-pipeline-item">
              <div className={`login-pipeline-dot ${i === activeStep ? "active" : i < activeStep ? "done" : ""}`}>
                <span>{step.icon}</span>
              </div>
              <span className={`login-pipeline-label ${i === activeStep ? "active" : ""}`}>
                {step.label}
              </span>
              {i < PIPELINE_STEPS.length - 1 && (
                <div className={`login-pipeline-line ${i < activeStep ? "done" : ""}`} />
              )}
            </div>
          ))}
        </div>

        {/* Divider */}
        <div className="login-divider">
          <span>Masuk untuk mulai</span>
        </div>

        {/* Google button */}
        <button
          onClick={handleGoogleLogin}
          disabled={loading}
          className="login-google-btn"
        >
          {loading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <svg className="login-google-icon" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
            </svg>
          )}
          <span>{loading ? "Mengalihkan…" : "Masuk dengan Google"}</span>
        </button>

        {error && <p className="login-error">{error}</p>}

        {/* Feature highlights */}
        <div className="login-features">
          {[
            { label: "Transkripsi GPU", desc: "Whisper large-v3" },
            { label: "AI Viral Scoring", desc: "Claude Sonnet" },
            { label: "Auto-cut & Publish", desc: "FFmpeg + YouTube" },
          ].map((f) => (
            <div key={f.label} className="login-feature-item">
              <div className="login-feature-dot" />
              <div>
                <p className="login-feature-label">{f.label}</p>
                <p className="login-feature-desc">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <style>{`
        .login-root {
          min-height: 100vh;
          background: #080810;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 1rem;
          position: relative;
          overflow: hidden;
          font-family: 'Inter', sans-serif;
        }

        /* Animated background orbs */
        .login-bg { position: absolute; inset: 0; pointer-events: none; }

        .login-orb {
          position: absolute;
          border-radius: 50%;
          filter: blur(80px);
          animation: orbFloat 8s ease-in-out infinite;
        }
        .login-orb-1 {
          width: 500px; height: 500px;
          background: radial-gradient(circle, rgba(108,99,255,0.18) 0%, transparent 70%);
          top: -150px; left: -150px;
          animation-delay: 0s;
        }
        .login-orb-2 {
          width: 400px; height: 400px;
          background: radial-gradient(circle, rgba(0,212,170,0.14) 0%, transparent 70%);
          bottom: -100px; right: -100px;
          animation-delay: 3s;
        }
        .login-orb-3 {
          width: 300px; height: 300px;
          background: radial-gradient(circle, rgba(255,107,107,0.10) 0%, transparent 70%);
          top: 50%; left: 60%;
          animation-delay: 5s;
        }
        @keyframes orbFloat {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(30px, -20px) scale(1.05); }
          66% { transform: translate(-20px, 15px) scale(0.97); }
        }

        .login-grid {
          position: absolute; inset: 0;
          background-image:
            linear-gradient(rgba(108,99,255,0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(108,99,255,0.04) 1px, transparent 1px);
          background-size: 48px 48px;
          mask-image: radial-gradient(ellipse 80% 80% at 50% 50%, black 40%, transparent 100%);
        }

        /* Card */
        .login-card {
          position: relative;
          width: 100%;
          max-width: 420px;
          background: rgba(13, 13, 22, 0.85);
          backdrop-filter: blur(24px);
          border: 1px solid rgba(108,99,255,0.18);
          border-radius: 20px;
          padding: 2.5rem 2rem;
          box-shadow:
            0 0 0 1px rgba(108,99,255,0.08),
            0 40px 80px rgba(0,0,0,0.6),
            0 0 60px rgba(108,99,255,0.06);
          animation: cardIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        @keyframes cardIn {
          from { opacity: 0; transform: translateY(24px) scale(0.97); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }

        /* Logo */
        .login-logo {
          display: flex;
          align-items: center;
          gap: 14px;
          margin-bottom: 2rem;
        }
        .login-logo-icon {
          width: 52px; height: 52px;
          border-radius: 14px;
          background: rgba(108,99,255,0.12);
          border: 1px solid rgba(108,99,255,0.25);
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
        }
        .login-title {
          font-family: 'Space Grotesk', sans-serif;
          font-size: 1.25rem;
          font-weight: 700;
          color: #E8E8F0;
          margin: 0;
          letter-spacing: -0.02em;
        }
        .login-subtitle {
          font-size: 0.78rem;
          color: #6B6B8A;
          margin: 2px 0 0 0;
          font-family: 'JetBrains Mono', monospace;
        }

        /* Pipeline */
        .login-pipeline {
          display: flex;
          align-items: flex-start;
          gap: 0;
          margin-bottom: 1.75rem;
          padding: 1rem;
          background: rgba(108,99,255,0.04);
          border: 1px solid rgba(108,99,255,0.1);
          border-radius: 12px;
        }
        .login-pipeline-item {
          display: flex;
          flex-direction: column;
          align-items: center;
          flex: 1;
          position: relative;
        }
        .login-pipeline-dot {
          width: 36px; height: 36px;
          border-radius: 50%;
          background: rgba(30,30,46,0.8);
          border: 1.5px solid rgba(108,99,255,0.15);
          display: flex; align-items: center; justify-content: center;
          font-size: 14px;
          transition: all 0.4s ease;
          position: relative;
          z-index: 1;
        }
        .login-pipeline-dot.active {
          background: rgba(108,99,255,0.2);
          border-color: #6C63FF;
          box-shadow: 0 0 16px rgba(108,99,255,0.4), 0 0 4px rgba(108,99,255,0.6);
          transform: scale(1.15);
        }
        .login-pipeline-dot.done {
          background: rgba(0,212,170,0.1);
          border-color: rgba(0,212,170,0.4);
        }
        .login-pipeline-label {
          font-size: 0.6rem;
          font-family: 'JetBrains Mono', monospace;
          color: #6B6B8A;
          margin-top: 6px;
          text-align: center;
          transition: color 0.3s;
          white-space: nowrap;
        }
        .login-pipeline-label.active {
          color: #6C63FF;
          font-weight: 600;
        }
        .login-pipeline-line {
          position: absolute;
          top: 18px;
          left: calc(50% + 18px);
          width: calc(100% - 36px);
          height: 1px;
          background: rgba(108,99,255,0.12);
          transition: background 0.4s;
        }
        .login-pipeline-line.done {
          background: rgba(0,212,170,0.35);
        }

        /* Divider */
        .login-divider {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 1rem;
        }
        .login-divider::before,
        .login-divider::after {
          content: '';
          flex: 1;
          height: 1px;
          background: rgba(108,99,255,0.12);
        }
        .login-divider span {
          font-size: 0.72rem;
          color: #6B6B8A;
          font-family: 'JetBrains Mono', monospace;
          white-space: nowrap;
        }

        /* Google button */
        .login-google-btn {
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
          padding: 13px 20px;
          background: rgba(255,255,255,0.96);
          color: #1a1a2e;
          font-weight: 600;
          font-size: 0.92rem;
          border-radius: 12px;
          border: none;
          cursor: pointer;
          transition: all 0.2s ease;
          box-shadow: 0 2px 16px rgba(0,0,0,0.4);
        }
        .login-google-btn:hover:not(:disabled) {
          background: white;
          transform: translateY(-1px);
          box-shadow: 0 6px 24px rgba(0,0,0,0.5), 0 0 20px rgba(108,99,255,0.15);
        }
        .login-google-btn:active:not(:disabled) {
          transform: translateY(0);
        }
        .login-google-btn:disabled {
          opacity: 0.7;
          cursor: not-allowed;
        }
        .login-google-icon { width: 20px; height: 20px; flex-shrink: 0; }

        /* Error */
        .login-error {
          margin-top: 0.75rem;
          text-align: center;
          font-size: 0.8rem;
          color: #FF6B6B;
          font-family: 'JetBrains Mono', monospace;
        }

        /* Features */
        .login-features {
          margin-top: 1.75rem;
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
          padding-top: 1.5rem;
          border-top: 1px solid rgba(108,99,255,0.1);
        }
        .login-feature-item {
          display: flex;
          align-items: flex-start;
          gap: 10px;
        }
        .login-feature-dot {
          width: 6px; height: 6px;
          border-radius: 50%;
          background: #6C63FF;
          margin-top: 5px;
          flex-shrink: 0;
          box-shadow: 0 0 6px rgba(108,99,255,0.6);
        }
        .login-feature-label {
          font-size: 0.82rem;
          font-weight: 600;
          color: #C8C8D8;
          margin: 0;
        }
        .login-feature-desc {
          font-size: 0.72rem;
          color: #6B6B8A;
          margin: 1px 0 0 0;
          font-family: 'JetBrains Mono', monospace;
        }
      `}</style>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: "100vh", background: "#080810" }} />}>
      <LoginContent />
    </Suspense>
  );
}
