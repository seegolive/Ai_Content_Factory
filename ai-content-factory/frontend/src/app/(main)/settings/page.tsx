"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import {
  User, Youtube, Shield, LogOut, CheckCircle, AlertTriangle, ExternalLink, RefreshCw,
  Crop, ChevronRight,
} from "lucide-react";
import { Header } from "@/components/layout/Header";
import { useYoutubeStats } from "@/lib/queries";
import { authApi } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

function formatSubs(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export default function SettingsPage() {
  const router = useRouter();
  const { data: ytData, isLoading: ytLoading, refetch: refetchYt } = useYoutubeStats();
  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => authApi.getMe().then((r) => r.data),
    staleTime: 60_000,
  });

  const handleLogout = async () => {
    try { await authApi.logout(); } finally {
      if (typeof window !== "undefined") {
        localStorage.removeItem("access_token");
        window.location.href = "/login";
      }
    }
  };

  const handleConnectYoutube = async () => {
    try {
      const { data } = await authApi.getLoginUrl();
      window.location.href = data.auth_url;
    } catch {
      toast.error("Failed to get login URL");
    }
  };

  return (
    <>
      <Header breadcrumb={[{ label: "Settings" }]} />

      <div className="page-scroll">
        <div className="settings-body">

          {/* Profile Section */}
          <div className="settings-section anim-0">
            <div className="settings-section-hd">
              <div className="settings-section-icon" style={{ background: "var(--primary-dim)" }}>
                <User size={13} color="var(--primary-text)" />
              </div>
              <span className="settings-section-title">Profile</span>
            </div>
            <div className="settings-section-body">
              {me ? (
                <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 20 }}>
                  {me.avatar_url ? (
                    <Image
                      src={me.avatar_url}
                      alt={me.name ?? ""}
                      width={48}
                      height={48}
                      style={{ borderRadius: "50%", border: "2px solid var(--border-2)", objectFit: "cover" }}
                    />
                  ) : (
                    <div style={{
                      width: 48, height: 48, borderRadius: "50%",
                      background: "var(--primary-dim)", border: "1px solid rgba(124,111,255,0.3)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 18, fontWeight: 700, color: "var(--primary-text)",
                    }}>
                      {me.name?.[0]?.toUpperCase() ?? me.email[0].toUpperCase()}
                    </div>
                  )}
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: "var(--text-1)", marginBottom: 2 }}>
                      {me.name ?? "—"}
                    </div>
                    <div style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--text-3)" }}>
                      {me.email}
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ height: 48, marginBottom: 20, display: "flex", alignItems: "center" }}>
                  <div className="skeleton" style={{ width: 48, height: 48, borderRadius: "50%", flexShrink: 0 }} />
                  <div style={{ marginLeft: 14 }}>
                    <div className="skeleton" style={{ width: 120, height: 14, borderRadius: 4, marginBottom: 8 }} />
                    <div className="skeleton" style={{ width: 180, height: 12, borderRadius: 4 }} />
                  </div>
                </div>
              )}

              <div className="settings-field">
                <div className="settings-label">Email</div>
                <input
                  className="settings-input"
                  type="email"
                  value={me?.email ?? ""}
                  disabled
                  placeholder="Loading..."
                />
              </div>
              <div className="settings-field">
                <div className="settings-label">Plan</div>
                <input
                  className="settings-input"
                  type="text"
                  value={me?.plan ? me.plan.charAt(0).toUpperCase() + me.plan.slice(1) : ""}
                  disabled
                  placeholder="Loading..."
                />
              </div>
            </div>
          </div>

          {/* YouTube Section */}
          <div className="settings-section anim-1">
            <div className="settings-section-hd">
              <div className="settings-section-icon" style={{ background: "var(--danger-dim)" }}>
                <Youtube size={13} color="var(--danger)" />
              </div>
              <span className="settings-section-title">YouTube Accounts</span>
              <button
                className="icon-btn"
                style={{ marginLeft: "auto" }}
                onClick={() => refetchYt()}
                title="Refresh"
              >
                <RefreshCw size={13} />
              </button>
            </div>
            <div className="settings-section-body">
              {ytLoading ? (
                <div>
                  {[1, 2].map((i) => (
                    <div key={i} className="yt-account-row" style={{ marginBottom: 10 }}>
                      <div className="skeleton" style={{ width: 36, height: 36, borderRadius: "50%" }} />
                      <div style={{ flex: 1 }}>
                        <div className="skeleton" style={{ width: 140, height: 13, borderRadius: 4, marginBottom: 6 }} />
                        <div className="skeleton" style={{ width: 90, height: 11, borderRadius: 4 }} />
                      </div>
                    </div>
                  ))}
                </div>
              ) : !ytData?.connected || ytData.accounts.length === 0 ? (
                <div>
                  <p style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 14, lineHeight: 1.6 }}>
                    No YouTube account connected. Connect your YouTube channel to enable direct publishing and channel analytics on the dashboard.
                  </p>
                  <button className="btn-primary" onClick={handleConnectYoutube}>
                    <Youtube size={13} />
                    Connect YouTube Account
                  </button>
                </div>
              ) : (
                <div>
                  {ytData.accounts.map((acc) => (
                    <div key={acc.channel_id} className="yt-account-row">
                      <div className="yt-avatar">
                        {acc.thumbnail_url
                          ? <Image src={acc.thumbnail_url} alt={acc.channel_name ?? ""} width={36} height={36} style={{ borderRadius: "50%", objectFit: "cover" }} />
                          : <Youtube size={16} color="var(--danger)" />}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="yt-channel-name">{acc.channel_name ?? acc.channel_id}</div>
                        <div className="yt-channel-meta">
                          {acc.subscriber_count !== undefined
                            ? `${formatSubs(acc.subscriber_count)} subscribers`
                            : acc.channel_id}
                        </div>
                      </div>
                      <div>
                        {acc.error ? (
                          <div className="yt-status-err">
                            <AlertTriangle size={11} />
                            {acc.error}
                          </div>
                        ) : (
                          <div className="yt-status-ok">
                            <CheckCircle size={11} />
                            Connected
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  <button
                    className="btn-ghost"
                    onClick={handleConnectYoutube}
                    style={{ marginTop: 6 }}
                  >
                    <Youtube size={12} />
                    Connect another account
                  </button>
                </div>
              )}
              <div style={{
                marginTop: 16, padding: "10px 14px",
                background: "var(--bg-2)",
                border: "1px solid var(--border-1)",
                borderRadius: "var(--r-md)",
                fontSize: 12, color: "var(--text-3)",
                fontFamily: "var(--font-mono)",
                lineHeight: 1.6,
              }}>
                <strong style={{ color: "var(--text-2)" }}>Why connect?</strong>
                {" "}Your YouTube account data (channel info, subscribers) is pulled via the Google OAuth token obtained at login. If it shows &ldquo;expired&rdquo;, sign out and sign in again to refresh the token.
              </div>
            </div>
          </div>

          {/* Vertical Crop Config */}
          <div className="settings-section anim-2">
            <div className="settings-section-hd">
              <div className="settings-section-icon" style={{ background: "rgba(34,197,94,0.12)" }}>
                <Crop size={13} color="#22c55e" />
              </div>
              <span className="settings-section-title">Vertical Crop</span>
            </div>
            <div className="settings-section-body">
              <p style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 14, lineHeight: 1.6 }}>
                Configure how your clips are cropped for vertical (9:16) format. Supports blur pillarbox, smart offset, and dual-zone (gameplay + facecam) modes with per-game overrides.
              </p>
              <Link
                href="/settings/crop-config"
                style={{
                  display: "inline-flex", alignItems: "center", gap: 7,
                  padding: "0 16px", height: 36,
                  borderRadius: "var(--r-md)",
                  background: "rgba(34,197,94,0.12)",
                  color: "#22c55e",
                  border: "1px solid rgba(34,197,94,0.2)",
                  fontSize: 13, fontWeight: 600, cursor: "pointer",
                  fontFamily: "var(--font-sans)",
                  textDecoration: "none",
                  transition: "all 130ms ease",
                }}
              >
                <Crop size={13} />
                Open Crop Config
                <ChevronRight size={12} style={{ marginLeft: 2 }} />
              </Link>
            </div>
          </div>

          {/* Account Section */}
          <div className="settings-section anim-3">
            <div className="settings-section-hd">
              <div className="settings-section-icon" style={{ background: "var(--danger-dim)" }}>
                <Shield size={13} color="var(--danger)" />
              </div>
              <span className="settings-section-title">Account</span>
            </div>
            <div className="settings-section-body">
              <p style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 16, lineHeight: 1.6 }}>
                You are signed in via Google OAuth. To change your account, sign out and sign back in with a different Google account.
              </p>
              <button
                onClick={handleLogout}
                style={{
                  display: "inline-flex", alignItems: "center", gap: 7,
                  padding: "0 16px", height: 36,
                  borderRadius: "var(--r-md)",
                  background: "var(--danger-dim)",
                  color: "var(--danger)",
                  border: "1px solid rgba(248,113,113,0.25)",
                  fontSize: 13, fontWeight: 600, cursor: "pointer",
                  fontFamily: "var(--font-sans)",
                  transition: "all 130ms ease",
                }}
              >
                <LogOut size={13} />
                Sign Out
              </button>
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
