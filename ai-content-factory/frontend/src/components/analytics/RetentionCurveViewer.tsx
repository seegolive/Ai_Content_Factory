"use client";
import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from "recharts";
import { useRetentionCurve } from "@/hooks/useAnalytics";
import { useVideosWithAnalytics } from "@/hooks/useAnalytics";
import { Zap, TrendingDown, Clock, Sparkles, ChevronRight } from "lucide-react";
import type { VideoWithAnalytics } from "@/types/analytics";

interface Props {
  channelId: string | null;
}

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number; payload: { timestamp_seconds: number } }>;
  label?: string;
  duration: number;
}

function CustomTooltip({ active, payload, label, duration }: CustomTooltipProps) {
  if (!active || !payload?.length || !label) return null;
  const elapsed = parseFloat(label);
  const ts = Math.round(elapsed * duration);
  return (
    <div className="recharts-custom-tooltip">
      <p style={{ color: "#6B6B8A", fontSize: 11, marginBottom: 2 }}>
        {formatTime(ts)} ({(elapsed * 100).toFixed(0)}% video)
      </p>
      <p style={{ color: "#00D4AA", fontWeight: 600 }}>
        {(payload[0].value * 100).toFixed(1)}% masih menonton
      </p>
    </div>
  );
}

export function RetentionCurveViewer({ channelId }: Props) {
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);

  // Only fetch videos that have retention data
  const { data: videosData } = useVideosWithAnalytics(channelId, { limit: 50 });
  const videosWithRetention: VideoWithAnalytics[] =
    videosData?.items?.filter((v) => v.has_retention_data && v.youtube_video_id) ?? [];

  const activeYtId = selectedVideoId ?? videosWithRetention[0]?.youtube_video_id ?? null;
  const { data: curve, isLoading, isError } = useRetentionCurve(activeYtId);

  const duration = curve?.duration_seconds ?? 1;
  const chartData = curve?.data_points ?? [];

  return (
    <div className="panel analytics-chart-panel">
      <div className="analytics-chart-header">
        <div>
          <h3 className="analytics-section-title">
            Audience Retention Analysis
            <span className="analytics-ai-badge">
              <Sparkles size={10} /> AI-Powered
            </span>
          </h3>
        </div>
        {videosWithRetention.length > 0 && (
          <select
            className="analytics-select"
            value={activeYtId ?? ""}
            onChange={(e) => setSelectedVideoId(e.target.value || null)}
          >
            {videosWithRetention.map((v) => (
              <option key={v.youtube_video_id} value={v.youtube_video_id}>
                {v.title.slice(0, 50)}
              </option>
            ))}
          </select>
        )}
      </div>

      {videosWithRetention.length === 0 ? (
        <div className="analytics-retention-empty">
          <Clock size={32} strokeWidth={1.5} />
          <p>Data retention belum tersedia</p>
          <p className="muted">Video perlu minimal 1.000 views untuk retention data tersedia di YouTube Analytics.</p>
        </div>
      ) : isLoading ? (
        <div className="skeleton" style={{ height: 200, borderRadius: 8 }} />
      ) : isError || !curve || chartData.length === 0 ? (
        <div className="analytics-retention-empty">
          <p className="muted">Retention data tidak tersedia untuk video ini.</p>
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" aspect={16 / 5}>
            <LineChart data={chartData} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
              <XAxis
                dataKey="elapsed_ratio"
                tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                tick={{ fill: "#6B6B8A", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                tick={{ fill: "#6B6B8A", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={42}
                domain={[0, 1]}
              />
              {/* YouTube avg benchmark */}
              <ReferenceLine y={0.4} stroke="#6B6B8A" strokeDasharray="4 4" label={{ value: "YouTube avg", fill: "#6B6B8A", fontSize: 10 }} />

              {/* Peak moment highlight areas */}
              {(curve.peak_moments ?? []).slice(0, 3).map((peak, i) => (
                <ReferenceArea
                  key={i}
                  x1={Math.max(0, peak.elapsed_ratio - 0.02)}
                  x2={Math.min(1, peak.elapsed_ratio + 0.02)}
                  fill="#00D4AA"
                  fillOpacity={0.08}
                />
              ))}

              <Tooltip
                content={
                  <CustomTooltip
                    duration={duration}
                    active={undefined}
                    payload={undefined}
                    label={undefined}
                  />
                }
              />
              <Line
                type="monotone"
                dataKey="retention_ratio"
                stroke="#00D4AA"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: "#00D4AA" }}
              />
            </LineChart>
          </ResponsiveContainer>

          {/* Optimal Clip Windows */}
          {(curve.optimal_clip_windows ?? []).length > 0 && (
            <div className="retention-windows">
              <h4 className="retention-windows-title">
                <Zap size={14} /> Optimal Clip Windows
              </h4>
              <div className="retention-windows-list">
                {curve.optimal_clip_windows.map((w, i) => (
                  <div key={i} className="retention-window-card">
                    <div className="retention-window-info">
                      <span className="retention-window-time">
                        {formatTime(w.start)} — {formatTime(w.end)}
                      </span>
                      <span className="retention-score">{w.score}/100</span>
                    </div>
                    <p className="retention-window-reason">{w.reason}</p>
                    <button className="btn-ghost-sm" onClick={() => {}}>
                      Buat Clip dari Momen Ini <ChevronRight size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Drop-off alerts */}
          {(curve.drop_off_points ?? []).slice(0, 2).map((drop, i) => (
            <div key={i} className="retention-alert">
              <TrendingDown size={14} />
              <span>{drop.label}</span>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
