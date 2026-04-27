"use client";
import { Brain, RefreshCw, CheckCircle } from "lucide-react";
import { useContentDNA } from "@/hooks/useAnalytics";
import type { ContentDNAModel } from "@/types/analytics";

interface Props {
  channelId: string | null;
}

function ConfidenceBar({ value }: { value: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div className="analytics-bar-bg" style={{ flex: 1, height: 6 }}>
        <div
          className="analytics-bar-fill"
          style={{ width: `${value}%`, background: value >= 60 ? "#00D4AA" : value >= 30 ? "#F0B429" : "#FF6B6B" }}
        />
      </div>
      <span style={{ fontSize: 12, color: "#6B6B8A", minWidth: 36 }}>{value.toFixed(0)}%</span>
    </div>
  );
}

function WeightRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="dna-weight-row">
      <span className="dna-weight-label">{label.replace(/_/g, " ")}</span>
      <div className="analytics-bar-bg" style={{ flex: 1, height: 4 }}>
        <div
          className="analytics-bar-fill"
          style={{ width: `${(value * 100).toFixed(0)}%`, background: "#6C63FF" }}
        />
      </div>
      <span className="dna-weight-pct">{(value * 100).toFixed(0)}%</span>
    </div>
  );
}

export function ContentDNAPanel({ channelId }: Props) {
  const { data: dna, isLoading } = useContentDNA(channelId);

  if (isLoading) {
    return (
      <div className="panel" style={{ height: 280 }}>
        <div className="skeleton" style={{ height: "100%", borderRadius: 8 }} />
      </div>
    );
  }

  return (
    <div className="panel analytics-chart-panel">
      <div className="analytics-chart-header">
        <h3 className="analytics-section-title">
          <Brain size={16} /> Content DNA
          <span className="analytics-ai-badge">AI Learning</span>
        </h3>
        {dna?.last_updated && (
          <span className="muted" style={{ fontSize: 11 }}>
            Updated {new Date(dna.last_updated).toLocaleDateString("id-ID")}
          </span>
        )}
      </div>

      {!dna || dna.status === "building" ? (
        <div className="analytics-retention-empty">
          <RefreshCw size={28} strokeWidth={1.5} className="dna-building-icon" />
          <p>AI sedang mempelajari channel kamu</p>
          <p className="muted">{dna?.message ?? "Butuh lebih banyak video dengan analytics data."}</p>
        </div>
      ) : (
        <div className="dna-content">
          {/* Confidence */}
          <div className="dna-section">
            <div className="dna-label-row">
              <span className="dna-section-label">Model Confidence</span>
              <span className="dna-videos-analyzed">{dna.videos_analyzed} video dianalisis</span>
            </div>
            <ConfidenceBar value={dna.confidence_score} />
          </div>

          {/* Niche */}
          {dna.niche && (
            <div className="dna-section">
              <span className="dna-section-label">Niche</span>
              <div className="dna-tags">
                <span className="dna-tag primary">{dna.niche}</span>
                {(dna.sub_niches ?? []).slice(0, 3).map((s) => (
                  <span key={s} className="dna-tag">{s}</span>
                ))}
              </div>
            </div>
          )}

          {/* Viral Score Weights */}
          {Object.keys(dna.viral_score_weights ?? {}).length > 0 && (
            <div className="dna-section">
              <span className="dna-section-label">Viral Score Weights</span>
              <div className="dna-weights">
                {Object.entries(dna.viral_score_weights)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 4)
                  .map(([k, v]) => (
                    <WeightRow key={k} label={k} value={v as number} />
                  ))}
              </div>
            </div>
          )}

          {/* Best patterns */}
          {(dna.top_performing_patterns?.title_patterns ?? []).length > 0 && (
            <div className="dna-section">
              <span className="dna-section-label">Title Patterns Terbaik</span>
              <div className="dna-tags">
                {(dna.top_performing_patterns.title_patterns ?? []).slice(0, 4).map((p) => (
                  <span key={p} className="dna-tag success">
                    <CheckCircle size={9} /> {p}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Best clip duration */}
          {dna.top_performing_patterns?.best_clip_duration && (
            <div className="dna-section">
              <span className="dna-section-label">Durasi Clip Optimal</span>
              <span className="dna-stat-value">
                {dna.top_performing_patterns.best_clip_duration.min}–
                {dna.top_performing_patterns.best_clip_duration.max}s
                &nbsp;·&nbsp;
                <strong style={{ color: "#00D4AA" }}>
                  {dna.top_performing_patterns.best_clip_duration.optimal}s ideal
                </strong>
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
