"use client";
import { useRouter } from "next/navigation";
import { Zap, Clock, Gamepad2, ChevronRight, Flame } from "lucide-react";
import { useOpportunities } from "@/hooks/useAnalytics";
import { formatDistanceToNow, parseISO } from "date-fns";
import { id } from "date-fns/locale";

interface Props {
  channelId: string | null;
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h} jam ${m > 0 ? m + " mnt" : ""}`.trim();
  return `${m} menit`;
}

function ScoreBadge({ score }: { score: number }) {
  const cls = score >= 75 ? "score-high" : score >= 50 ? "score-mid" : "score-low";
  return <span className={`opportunity-score ${cls}`}>{score.toFixed(0)}/100</span>;
}

export function OpportunitiesSection({ channelId }: Props) {
  const router = useRouter();
  const { data: opportunities, isLoading } = useOpportunities(channelId);

  if (isLoading) {
    return (
      <div className="panel">
        <div className="skeleton" style={{ height: 140, borderRadius: 8 }} />
      </div>
    );
  }

  const items = opportunities ?? [];

  return (
    <div className="panel analytics-opportunities-panel">
      <div className="analytics-chart-header">
        <h3 className="analytics-section-title">
          <Zap size={16} /> Video Berpotensi Tinggi — Belum Diclip
        </h3>
        {items.length > 0 && (
          <span className="analytics-total-label">
            AI menemukan {items.length} video dengan momen viral yang belum diekstrak
          </span>
        )}
      </div>

      {items.length === 0 ? (
        <div className="analytics-empty-chart">
          Semua video sudah diproses! Upload video baru atau sync analytics.
        </div>
      ) : (
        <div className="opportunity-cards">
          {items.map((op) => (
            <div
              key={op.video_id}
              className={`opportunity-card ${op.viral_potential_score >= 75 ? "hot" : op.viral_potential_score >= 50 ? "mid" : "low"}`}
            >
              {op.viral_potential_score >= 75 && (
                <div className="opportunity-hot-badge">
                  <Flame size={11} /> HOT
                </div>
              )}

              <div className="opportunity-header">
                <div className="opportunity-title" title={op.title}>
                  {op.title.slice(0, 70)}{op.title.length > 70 ? "…" : ""}
                </div>
                <ScoreBadge score={op.viral_potential_score} />
              </div>

              <div className="opportunity-meta">
                <span>
                  <Clock size={11} />{" "}
                  {op.published_at
                    ? formatDistanceToNow(parseISO(op.published_at), { addSuffix: true, locale: id })
                    : ""}
                  {" · "}
                  {formatDuration(op.duration_seconds)}
                </span>
                {op.game_name && (
                  <span>
                    <Gamepad2 size={11} /> {op.game_name}
                  </span>
                )}
              </div>

              <div className="opportunity-stats">
                {op.peak_moments_count > 0 && (
                  <span className="op-stat">
                    📊 {op.peak_moments_count} peak moment terdeteksi
                  </span>
                )}
                <span className="op-stat">
                  ✂️ Estimasi {op.estimated_clips}–{op.estimated_clips + 4} clips
                </span>
              </div>

              <p className="opportunity-rec">{op.recommendation}</p>

              <div className="opportunity-actions">
                <button
                  className="btn-ghost-sm"
                  onClick={() => router.push(`/videos/${op.video_id}`)}
                >
                  Lihat Video
                </button>
                <button
                  className="btn-primary-sm"
                  onClick={() => router.push(`/videos?process=${op.video_id}`)}
                >
                  ▶ Proses Sekarang <ChevronRight size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
