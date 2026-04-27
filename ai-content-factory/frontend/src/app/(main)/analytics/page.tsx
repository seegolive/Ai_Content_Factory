"use client";
import { useState, useEffect } from "react";
import { RefreshCw, Youtube, Users, Eye, Clock, TrendingUp, CheckCircle } from "lucide-react";
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

  if (accounts.length === 0 || !accounts.some((a) => a.connected)) {
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

        {/* ── Header ── */}
        <div className="analytics-page-header">
          <div className="analytics-header-left">
            <h1 className="page-heading-title" style={{ margin: 0 }}>Analytics</h1>
            {accounts.length > 1 ? (
              <select
                className="analytics-select"
                value={selectedChannelId ?? ""}
                onChange={(e) => setSelectedChannelId(e.target.value || null)}
              >
                {accounts
                  .filter((a) => a.connected)
                  .map((a) => (
                    <option key={a.channel_id} value={a.channel_id}>
                      {a.channel_name ?? a.channel_id}
                    </option>
                  ))}
              </select>
            ) : (
              <span className="analytics-channel-name-label">
                {accounts[0]?.channel_name ?? accounts[0]?.channel_id}
              </span>
            )}
          </div>
          <div className="analytics-header-right">
            {lastSynced && (
              <span className="analytics-last-synced">
                <CheckCircle size={12} style={{ color: "#00D4AA" }} />
                Sync {lastSynced}
              </span>
            )}
            <button
              className="btn-secondary"
              onClick={() => syncAnalytics(selectedChannelId!)}
              disabled={isSyncing || !selectedChannelId}
            >
              <RefreshCw size={14} className={isSyncing ? "spin" : ""} />
              {isSyncing ? "Syncing..." : "Sync Analytics"}
            </button>
          </div>
        </div>

        {/* ── Channel Profile Card ── */}
        <div className="analytics-channel-card">
          <div className="analytics-channel-avatar-wrap">
            <Youtube size={24} />
          </div>
          <div className="analytics-channel-info">
            <div className="analytics-channel-card-title">
              {overviewLoading ? (
                <div className="skeleton" style={{ width: 160, height: 18, borderRadius: 4 }} />
              ) : (
                <span>{overview?.channel_name ?? accounts.find((a) => a.channel_id === selectedChannelId)?.channel_name ?? "—"}</span>
              )}
            </div>
            <div className="analytics-channel-card-meta">
              {overviewLoading ? (
                <div className="skeleton" style={{ width: 220, height: 14, borderRadius: 4 }} />
              ) : (
                <>
                  <span><Eye size={11} /> {(overview?.total_views ?? 0).toLocaleString()} total views</span>
                  <span>·</span>
                  <span><Users size={11} /> {(overview?.total_videos ?? 0).toLocaleString()} video</span>
                  {(overview?.content_dna_confidence ?? 0) > 0 && (
                    <>
                      <span>·</span>
                      <span style={{ color: "#00D4AA" }}>DNA {overview!.content_dna_confidence.toFixed(0)}% confidence</span>
                    </>
                  )}
                </>
              )}
            </div>
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
            value={overview?.watch_time_hours ?? 0}
            unit=" jam"
            icon={<Clock size={16} />}
            accentColor="teal"
            loading={overviewLoading}
          />
          <KPICard
            label="Avg CTR"
            value={overview ? parseFloat((overview.avg_ctr * 100).toFixed(1)) : 0}
            unit="%"
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
            value={overview?.subscribers_last_30d ?? 0}
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
