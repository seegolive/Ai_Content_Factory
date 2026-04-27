"use client";
import { useState, useEffect } from "react";
import { RefreshCw, Youtube, Users, Eye, Clock, TrendingUp, CheckCircle, ChevronDown } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { id } from "date-fns/locale";
import { useYoutubeStats } from "@/lib/queries";
import { useChannelOverview, useSyncAnalytics } from "@/hooks/useAnalytics";
import { KPICard } from "@/components/analytics/KPICard";
import { ViewsTrendChart } from "@/components/analytics/ViewsTrendChart";
import { GamePerformanceChart } from "@/components/analytics/GamePerformanceChart";
import { ContentDNAPanel } from "@/components/analytics/ContentDNAPanel";
import { RetentionCurveViewer } from "@/components/analytics/RetentionCurveViewer";
import { VideoPerformanceTable } from "@/components/analytics/VideoPerformanceTable";
import { OpportunitiesSection } from "@/components/analytics/OpportunitiesSection";
import { WeeklyInsightReport } from "@/components/analytics/WeeklyInsightReport";

export default function AnalyticsPage() {
  const { data: ytStats } = useYoutubeStats();
  const accounts = ytStats?.accounts ?? [];

  const [selectedChannelId, setSelectedChannelId] = useState<string | null>(null);

  // Auto-select first connected channel
  useEffect(() => {
    if (!selectedChannelId && accounts.length > 0) {
      const first = accounts.find((a) => a.connected);
      if (first) setSelectedChannelId(first.channel_id);
    }
  }, [accounts, selectedChannelId]);

  const { data: overview, isLoading: overviewLoading } = useChannelOverview(selectedChannelId);
  const { mutate: syncAnalytics, isPending: isSyncing } = useSyncAnalytics();

  const lastSynced = overview?.last_synced
    ? formatDistanceToNow(new Date(overview.last_synced), { addSuffix: true, locale: id })
    : null;

  // Detect stale data: total_views is 0 but we have recent views
  const hasStaleData = !overviewLoading && (overview?.total_views ?? 0) === 0 && (overview?.views_last_30d ?? 0) > 0;

  const connectedAccounts = accounts.filter((a) => a.connected);
  const selectedAccount = connectedAccounts.find((a) => a.channel_id === selectedChannelId);
  const channelName = overview?.channel_name ?? selectedAccount?.channel_name ?? "—";

  if (!ytStats) {
    return (
      <div className="page-scroll">
        <div className="page-body">
          <div className="analytics-kpi-row">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="skeleton" style={{ height: 88, borderRadius: 12 }} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (accounts.length === 0 || !connectedAccounts.length) {
    return (
      <div className="page-scroll">
        <div className="page-body">
          <div className="analytics-empty-state">
            <Youtube size={48} strokeWidth={1.5} />
            <h2>Hubungkan Channel YouTube</h2>
            <p>Pergi ke Settings → YouTube untuk menghubungkan channel kamu.</p>
            <a href="/settings" className="btn-primary" style={{ textDecoration: "none", marginTop: 12 }}>
              Buka Settings
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-scroll">
      <div className="page-body analytics-page">

        {/* ── Header Bar ── */}
        <div className="analytics-topbar">
          {/* Left: Channel identity */}
          <div className="analytics-topbar-left">
            <div className="analytics-channel-avatar-wrap">
              <Youtube size={18} />
            </div>
            <div className="analytics-topbar-identity">
              {connectedAccounts.length > 1 ? (
                <div className="analytics-channel-select-wrap">
                  <select
                    className="analytics-channel-select"
                    value={selectedChannelId ?? ""}
                    onChange={(e) => setSelectedChannelId(e.target.value || null)}
                  >
                    {connectedAccounts.map((a) => (
                      <option key={a.channel_id} value={a.channel_id}>
                        {a.channel_name ?? a.channel_id}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={13} className="analytics-channel-select-icon" />
                </div>
              ) : (
                <span className="analytics-topbar-channel-name">{channelName}</span>
              )}
              <div className="analytics-topbar-meta">
                {overviewLoading ? (
                  <div className="skeleton" style={{ width: 180, height: 11, borderRadius: 3 }} />
                ) : (
                  <>
                    <span>
                      <Eye size={10} />
                      {hasStaleData
                        ? `${(overview!.views_last_30d).toLocaleString()} views (30d)`
                        : `${(overview?.total_views ?? 0).toLocaleString()} total views`}
                    </span>
                    <span className="analytics-topbar-dot" />
                    <span>
                      <Users size={10} />
                      {(overview?.total_videos ?? 0).toLocaleString()} video
                    </span>
                    {(overview?.content_dna_confidence ?? 0) > 0 && (
                      <>
                        <span className="analytics-topbar-dot" />
                        <span style={{ color: "#00D4AA" }}>
                          DNA {overview!.content_dna_confidence.toFixed(0)}%
                        </span>
                      </>
                    )}
                    {hasStaleData && (
                      <>
                        <span className="analytics-topbar-dot" />
                        <span style={{ color: "#F0B429" }}>Sync untuk data lengkap</span>
                      </>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Right: Sync status + action */}
          <div className="analytics-topbar-right">
            {lastSynced && !isSyncing && (
              <span className="analytics-sync-status">
                <CheckCircle size={11} />
                {lastSynced}
              </span>
            )}
            <button
              className="analytics-sync-btn"
              onClick={() => syncAnalytics(selectedChannelId!)}
              disabled={isSyncing || !selectedChannelId}
            >
              <RefreshCw size={13} className={isSyncing ? "spin" : ""} />
              {isSyncing ? "Syncing..." : "Sync"}
            </button>
          </div>
        </div>

        {/* ── 4 KPI Cards ── */}
        <div className="analytics-kpi-row">
          <KPICard
            label="Views (30 Hari)"
            value={overview?.views_last_30d ?? 0}
            icon={<Eye size={16} />}
            accentColor="violet"
            loading={overviewLoading}
            trend={
              overview?.views_trend_pct != null
                ? {
                    value: Math.abs(overview.views_trend_pct),
                    direction: overview.views_trend_pct >= 0 ? "up" : "down",
                    period: "vs 30 hari lalu",
                  }
                : undefined
            }
          />
          <KPICard
            label="Watch Time"
            value={hasStaleData ? "—" : (overview?.watch_time_hours ?? 0)}
            unit={hasStaleData ? undefined : " jam"}
            icon={<Clock size={16} />}
            accentColor="teal"
            loading={overviewLoading}
          />
          <KPICard
            label="Avg CTR"
            value={overview ? `${(overview.avg_ctr * 100).toFixed(1)}%` : "0%"}
            icon={<TrendingUp size={16} />}
            accentColor={
              (overview?.avg_ctr ?? 0) >= 0.06
                ? "teal"
                : (overview?.avg_ctr ?? 0) >= 0.03
                ? "default"
                : "coral"
            }
            loading={overviewLoading}
          />
          <KPICard
            label="Subs Baru (30H)"
            value={(overview?.subscribers_last_30d ?? 0) < 0 ? "—" : (overview?.subscribers_last_30d ?? 0)}
            icon={<Users size={16} />}
            accentColor="default"
            loading={overviewLoading}
          />
        </div>

        {/* ── Views Trend Chart ── */}
        <ViewsTrendChart channelId={selectedChannelId} />

        {/* ── Game Performance + Content DNA ── */}
        <div className="analytics-two-col">
          <GamePerformanceChart channelId={selectedChannelId} />
          <ContentDNAPanel channelId={selectedChannelId} />
        </div>

        {/* ── Retention Curve ── */}
        <RetentionCurveViewer channelId={selectedChannelId} />

        {/* ── Video Performance Table ── */}
        <VideoPerformanceTable channelId={selectedChannelId} />

        {/* ── Opportunities ── */}
        <OpportunitiesSection channelId={selectedChannelId} />

        {/* ── Weekly Report ── */}
        <WeeklyInsightReport channelId={selectedChannelId} />

      </div>
    </div>
  );
}
