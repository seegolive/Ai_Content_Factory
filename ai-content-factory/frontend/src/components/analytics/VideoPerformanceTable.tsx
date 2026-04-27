"use client";
import { useState, useMemo } from "react";
import Image from "next/image";
import { ChevronUp, ChevronDown, Eye, Clock, BarChart2, Scissors, Play, Youtube } from "lucide-react";
import { format, parseISO, formatDistanceToNow } from "date-fns";
import { id } from "date-fns/locale";
import { useVideosWithAnalytics } from "@/hooks/useAnalytics";
import type { VideoWithAnalytics } from "@/types/analytics";

interface Props {
  channelId: string | null;
}

type SortKey = "views" | "ctr" | "watch_time" | "published_at";

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function CTRBadge({ ctr }: { ctr: number }) {
  const pct = (ctr * 100).toFixed(1);
  const cls = ctr >= 0.06 ? "ctr-good" : ctr >= 0.03 ? "ctr-mid" : "ctr-bad";
  return <span className={`ctr-badge ${cls}`}>{pct}%</span>;
}

function ViewsBar({ views, maxViews }: { views: number; maxViews: number }) {
  const pct = maxViews > 0 ? Math.round((views / maxViews) * 100) : 0;
  return (
    <div className="analytics-bar-wrap" style={{ gap: 6 }}>
      <div className="analytics-bar-bg" style={{ width: 60 }}>
        <div className="analytics-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="analytics-bar-label">
        {views >= 1000 ? (views / 1000).toFixed(1) + "K" : views}
      </span>
    </div>
  );
}

const PAGE_SIZE = 20;

export function VideoPerformanceTable({ channelId }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("views");
  const [offset, setOffset] = useState(0);

  const { data, isLoading } = useVideosWithAnalytics(channelId, {
    limit: PAGE_SIZE,
    offset,
    sort_by: sortKey,
  });

  const videos = data?.items ?? [];
  const total = data?.total ?? 0;
  const maxViews = useMemo(() => Math.max(...videos.map((v) => v.views), 1), [videos]);

  function SortHeader({ label, field }: { label: string; field: SortKey }) {
    const active = sortKey === field;
    return (
      <th
        className={`vtable-th sortable${active ? " active" : ""}`}
        onClick={() => { setSortKey(field); setOffset(0); }}
      >
        {label}
        {active ? <ChevronDown size={12} /> : <ChevronUp size={12} style={{ opacity: 0.3 }} />}
      </th>
    );
  }

  return (
    <div className="panel analytics-table-panel">
      <div className="analytics-chart-header">
        <h3 className="analytics-section-title">
          <BarChart2 size={16} /> Video Performance
        </h3>
        <span className="analytics-total-label">{total} video</span>
      </div>

      {isLoading ? (
        <div>
          {[...Array(5)].map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 52, borderRadius: 6, marginBottom: 6 }} />
          ))}
        </div>
      ) : videos.length === 0 ? (
        <div className="analytics-empty-chart">
          Sync analytics untuk melihat data performa video.
        </div>
      ) : (
        <div className="vtable-wrap">
          <table className="vtable">
            <thead>
              <tr>
                <th className="vtable-th" style={{ width: 240 }}>Video</th>
                <SortHeader label="Views" field="views" />
                <SortHeader label="CTR" field="ctr" />
                <SortHeader label="Watch Time" field="watch_time" />
                <th className="vtable-th">Avg Duration</th>
                <SortHeader label="Published" field="published_at" />
                <th className="vtable-th">Clips</th>
              </tr>
            </thead>
            <tbody>
              {videos.map((v) => (
                <VideoRow key={v.video_id} video={v} maxViews={maxViews} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {total > PAGE_SIZE && (
        <div className="vtable-pagination">
          <button
            className="btn-ghost-sm"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            ← Prev
          </button>
          <span className="muted" style={{ fontSize: 12 }}>
            {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
          </span>
          <button
            className="btn-ghost-sm"
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}

function VideoRow({ video, maxViews }: { video: VideoWithAnalytics; maxViews: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr
        className={`vtable-row${expanded ? " expanded" : ""}`}
        onClick={() => setExpanded((e) => !e)}
      >
        <td className="vtable-td">
          <div className="vtable-video-cell">
            <div className="vtable-thumb">
              <Youtube size={14} className="vtable-thumb-icon" />
            </div>
            <div className="vtable-video-info">
              <span className="vtable-title" title={video.title}>
                {video.title.slice(0, 55)}{video.title.length > 55 ? "…" : ""}
              </span>
              <span className="vtable-duration">{formatDuration(video.duration_seconds)}</span>
            </div>
          </div>
        </td>
        <td className="vtable-td">
          <ViewsBar views={video.views} maxViews={maxViews} />
        </td>
        <td className="vtable-td">
          <CTRBadge ctr={video.avg_ctr} />
        </td>
        <td className="vtable-td vtable-mono">
          {Math.round(video.watch_time_minutes)}m
        </td>
        <td className="vtable-td vtable-mono">
          {formatDuration(Math.round(video.avg_view_duration_seconds))}
        </td>
        <td className="vtable-td vtable-muted">
          {video.published_at
            ? formatDistanceToNow(parseISO(video.published_at), { addSuffix: true, locale: id })
            : "—"}
        </td>
        <td className="vtable-td">
          {video.clips_generated > 0 ? (
            <span className="clips-badge">{video.clips_generated} clips</span>
          ) : video.clippable ? (
            <span className="clips-badge clippable">Belum diclip</span>
          ) : (
            <span className="vtable-muted">—</span>
          )}
        </td>
      </tr>
      {expanded && (
        <tr className="vtable-expanded-row">
          <td colSpan={7} className="vtable-td">
            <div className="vtable-expanded-content">
              <div className="vtable-stat-pair">
                <span className="vtable-stat-label">Watch %</span>
                <span className="vtable-stat-val">{video.avg_view_percentage.toFixed(1)}%</span>
              </div>
              <div className="vtable-stat-pair">
                <span className="vtable-stat-label">Retention Data</span>
                <span className="vtable-stat-val">{video.has_retention_data ? "✅ Tersedia" : "❌ Tidak tersedia"}</span>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
