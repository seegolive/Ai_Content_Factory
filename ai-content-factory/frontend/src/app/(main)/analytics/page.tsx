"use client";
import { BarChart2, TrendingUp, Eye, ThumbsUp, MessageSquare, Clock, Zap, Youtube } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { useYoutubeAnalytics } from "@/lib/queries";
import type { YTVideoStat } from "@/lib/api";

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatCount(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "K";
  return n.toLocaleString();
}

function formatSeconds(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function avgViews(total_views: number, total_videos: number): string {
  if (total_videos === 0) return "—";
  return formatCount(Math.round(total_views / total_videos));
}

// ── Sub-components ────────────────────────────────────────────────────────────

function KPISkeleton() {
  return (
    <div className="analytics-kpi-row">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="analytics-kpi-card anim-0">
          <div className="skeleton" style={{ height: 12, width: 70, borderRadius: 4, marginBottom: 8 }} />
          <div className="skeleton" style={{ height: 32, width: 90, borderRadius: 4 }} />
        </div>
      ))}
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="panel" style={{ marginTop: 8 }}>
      <div className="analytics-table-inner">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} style={{ display: "flex", gap: 12, padding: "12px 16px", borderBottom: "1px solid var(--border-1)" }}>
            <div className="skeleton" style={{ height: 27, width: 48, borderRadius: 4, flexShrink: 0 }} />
            <div className="skeleton" style={{ flex: 1, height: 16, borderRadius: 4 }} />
            <div className="skeleton" style={{ height: 16, width: 60, borderRadius: 4 }} />
          </div>
        ))}
      </div>
    </div>
  );
}

function VideoRow({ video, maxViews }: { video: YTVideoStat; maxViews: number }) {
  const pct = maxViews > 0 ? Math.round((video.views / maxViews) * 100) : 0;
  return (
    <div className="analytics-table-row">
      {/* Thumbnail */}
      <div>
        {video.thumbnail_url ? (
          <img className="analytics-thumb" src={video.thumbnail_url} alt="" />
        ) : (
          <div className="analytics-thumb-placeholder">
            <Youtube size={12} />
          </div>
        )}
      </div>

      {/* Title + date */}
      <div style={{ minWidth: 0, paddingRight: 12 }}>
        <div className="analytics-video-title">{video.title}</div>
        <div className="analytics-video-date">{formatDate(video.published_at)} · {formatSeconds(video.duration_seconds)}</div>
      </div>

      {/* Views bar */}
      <div className="analytics-bar-wrap">
        <div className="analytics-bar-bg">
          <div className="analytics-bar-fill" style={{ width: `${pct}%` }} />
        </div>
        <span className="analytics-bar-label">{formatCount(video.views)}</span>
      </div>

      {/* Likes */}
      <div className="analytics-stat-cell">{formatCount(video.likes)}</div>

      {/* Comments */}
      <div className="analytics-stat-cell">{formatCount(video.comments)}</div>

      {/* Duration */}
      <div className="analytics-stat-cell" style={{ fontFamily: "var(--font-mono)" }}>
        {formatSeconds(video.duration_seconds)}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const { data, isLoading, isError } = useYoutubeAnalytics();

  const analytics = data?.analytics ?? null;
  const connected = data?.connected ?? false;
  const errorMsg = data?.error;

  const maxViews = analytics?.recent_videos?.reduce((m, v) => Math.max(m, v.views), 0) ?? 0;

  return (
    <>
      <Header breadcrumb={[{ label: "Analytics" }]} />

      <div className="page-scroll">
        <div className="page-body">

        {/* Loading */}
        {isLoading && (
          <>
            <div className="page-heading">
              <div className="page-heading-eyebrow">YouTube</div>
              <h1 className="page-heading-title">Analytics</h1>
            </div>
            <KPISkeleton />
            <TableSkeleton />
          </>
        )}

        {/* Error / not connected */}
        {!isLoading && (!connected || !analytics) && (
          <div className="analytics-empty">
            <div className="analytics-empty-icon">
              <BarChart2 size={24} />
            </div>
            <div className="analytics-empty-title">No YouTube Channel Connected</div>
            <div className="analytics-empty-desc">
              {errorMsg
                ? errorMsg
                : "Connect your YouTube account in Settings to view channel analytics, subscriber counts, and per-video performance data."}
            </div>
            <a href="/settings" className="btn-primary" style={{ display: "inline-flex", alignItems: "center", gap: 6, marginTop: 4, textDecoration: "none" }}>
              <Youtube size={14} /> Go to Settings
            </a>
          </div>
        )}

        {/* Connected & data loaded */}
        {!isLoading && connected && analytics && (
          <>
            {/* Page heading */}
            <div className="page-heading">
              <div className="page-heading-eyebrow">YouTube</div>
              <h1 className="page-heading-title">
                Analytics <span className="gradient">Dashboard</span>
              </h1>
              <p style={{ fontSize: 13, color: "var(--text-3)", marginTop: 4 }}>
                Channel performance from YouTube Data API · Last 20 uploaded videos
              </p>
            </div>

            {/* Channel header card */}
            <div className="analytics-channel-header">
              {analytics.thumbnail_url ? (
                <img className="analytics-channel-avatar" src={analytics.thumbnail_url} alt={analytics.channel_name} />
              ) : (
                <div className="analytics-channel-avatar-placeholder">
                  {analytics.channel_name.charAt(0).toUpperCase()}
                </div>
              )}
              <div>
                <div className="analytics-channel-name">{analytics.channel_name}</div>
                <div className="analytics-channel-meta">
                  {analytics.channel_id} · {formatCount(analytics.total_videos)} videos
                </div>
              </div>
              <div className="analytics-channel-badge">
                <Zap size={10} /> Connected
              </div>
            </div>

            {/* KPI row */}
            <div className="analytics-kpi-row">
              <div className="analytics-kpi-card">
                <div className="analytics-kpi-label">Subscribers</div>
                <div className="analytics-kpi-value analytics-kpi-accent">
                  {formatCount(analytics.subscriber_count)}
                </div>
                <div className="analytics-kpi-sub">Total subscribers</div>
              </div>
              <div className="analytics-kpi-card">
                <div className="analytics-kpi-label">Total Views</div>
                <div className="analytics-kpi-value analytics-kpi-accent-green">
                  {formatCount(analytics.total_views)}
                </div>
                <div className="analytics-kpi-sub">All-time channel views</div>
              </div>
              <div className="analytics-kpi-card">
                <div className="analytics-kpi-label">Videos</div>
                <div className="analytics-kpi-value">
                  {analytics.total_videos.toLocaleString()}
                </div>
                <div className="analytics-kpi-sub">Published videos</div>
              </div>
              <div className="analytics-kpi-card">
                <div className="analytics-kpi-label">Avg Views / Video</div>
                <div className="analytics-kpi-value">
                  {avgViews(analytics.total_views, analytics.total_videos)}
                </div>
                <div className="analytics-kpi-sub">Across all uploads</div>
              </div>
            </div>

            {/* Two-column: recent video table + top 5 */}
            <div className="two-col-grid" style={{ gap: 16 }}>

              {/* Recent videos table */}
              <div className="panel">
                <div className="analytics-section-title">
                  Recent Videos — Performance
                </div>
                <div className="analytics-table-inner">
                  <div className="analytics-table-header">
                    <div className="analytics-table-header-cell"> </div>
                    <div className="analytics-table-header-cell">Title</div>
                    <div className="analytics-table-header-cell">Views</div>
                    <div className="analytics-table-header-cell">Likes</div>
                    <div className="analytics-table-header-cell">Comments</div>
                    <div className="analytics-table-header-cell">Duration</div>
                  </div>
                  {analytics.recent_videos.length === 0 ? (
                    <div style={{ padding: "32px 16px", textAlign: "center", color: "var(--text-3)", fontSize: 13 }}>
                      No videos found on this channel
                    </div>
                  ) : (
                    analytics.recent_videos.map((v) => (
                      <VideoRow key={v.video_id} video={v} maxViews={maxViews} />
                    ))
                  )}
                </div>
              </div>

              {/* Right column: Top 5 + Upgrade */}
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

                {/* Top 5 videos */}
                {analytics.top_videos.length > 0 && (
                  <div className="panel">
                    <div className="analytics-section-title">
                      <TrendingUp size={13} style={{ display: "inline", marginRight: 6, verticalAlign: -2 }} />
                      Top Videos by Views
                    </div>
                    <div style={{ padding: "4px 16px 12px" }}>
                      {analytics.top_videos.map((v, i) => (
                        <div key={v.video_id} className="analytics-top-row">
                          <div className="analytics-top-rank">#{i + 1}</div>
                          {v.thumbnail_url && (
                            <img className="analytics-thumb" src={v.thumbnail_url} alt="" />
                          )}
                          <div className="analytics-top-title">{v.title}</div>
                          <div className="analytics-top-views">
                            <Eye size={10} style={{ display: "inline", marginRight: 3, verticalAlign: -1 }} />
                            {formatCount(v.views)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Upgrade panel */}
                <div className="analytics-upgrade-panel">
                  <div className="analytics-upgrade-icon">
                    <BarChart2 size={18} />
                  </div>
                  <div>
                    <div className="analytics-upgrade-title">Unlock Time-Series Analytics</div>
                    <div className="analytics-upgrade-desc">
                      Add <code style={{ fontSize: 11, background: "rgba(255,255,255,0.08)", padding: "1px 5px", borderRadius: 3 }}>yt-analytics.readonly</code> scope
                      to view daily views, watch time, and audience retention graphs.
                    </div>
                  </div>
                  <a
                    href="/settings"
                    className="analytics-upgrade-btn"
                    style={{ textDecoration: "none" }}
                  >
                    Upgrade Scope
                  </a>
                </div>
              </div>
            </div>
          </>
        )}
        </div>
      </div>
    </>
  );
}
