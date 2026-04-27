"use client";
import {
  TrendingUp, AlertCircle, Lightbulb, CheckCircle,
  Bell, ChevronDown, ChevronUp, Clock, Zap, FileDown,
} from "lucide-react";
import { useState } from "react";
import { useWeeklyReport } from "@/hooks/useAnalytics";
import { format, parseISO, addDays, startOfWeek } from "date-fns";
import { id } from "date-fns/locale";
import type { WeeklyInsightReport as ReportType } from "@/types/analytics";

interface Props {
  channelId: string | null;
}

/* ── Simple bullet section (wins / issues) ── */
function Section({
  icon,
  title,
  items,
  accentColor,
  accentBg,
}: {
  icon: React.ReactNode;
  title: string;
  items: string[];
  accentColor: string;
  accentBg: string;
}) {
  const [open, setOpen] = useState(true);
  if (!items?.length) return null;
  return (
    <div className="wrep-section">
      <button className="wrep-section-hd" onClick={() => setOpen((o) => !o)}>
        <span className="wrep-section-icon" style={{ color: accentColor, background: accentBg }}>
          {icon}
        </span>
        <span className="wrep-section-title" style={{ color: accentColor }}>{title}</span>
        <span className="wrep-section-pill" style={{ background: accentBg, color: accentColor }}>
          {items.length}
        </span>
        <span className="wrep-chevron">
          {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </span>
      </button>
      {open && (
        <ul className="wrep-bullet-list">
          {items.map((item, i) => (
            <li key={i} className="wrep-bullet-item">
              <span className="wrep-dot" style={{ background: accentColor }} />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ── Action-card recommendations section ── */
function RecsSection({ recs }: { recs: NonNullable<ReportType["recommendations"]> }) {
  const [open, setOpen] = useState(true);
  if (!recs?.length) return null;

  const priority: Record<string, { label: string; color: string; bg: string }> = {
    high:   { label: "HIGH",  color: "#FF6B6B", bg: "rgba(255,107,107,0.12)" },
    medium: { label: "MED",   color: "#F0B429", bg: "rgba(240,180,41,0.12)"  },
    low:    { label: "LOW",   color: "#8B85FF", bg: "rgba(139,133,255,0.12)" },
  };

  return (
    <div className="wrep-section">
      <button className="wrep-section-hd" onClick={() => setOpen((o) => !o)}>
        <span className="wrep-section-icon" style={{ color: "#8B85FF", background: "rgba(139,133,255,0.12)" }}>
          <Lightbulb size={13} />
        </span>
        <span className="wrep-section-title" style={{ color: "#8B85FF" }}>Rekomendasi Aksi</span>
        <span className="wrep-section-pill" style={{ background: "rgba(139,133,255,0.12)", color: "#8B85FF" }}>
          {recs.length}
        </span>
        <span className="wrep-chevron">
          {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </span>
      </button>
      {open && (
        <div className="wrep-recs-list">
          {recs.map((rec, i) => {
            const p = priority[rec.priority] ?? priority.medium;
            return (
              <div key={i} className="wrep-rec-card">
                <span className="wrep-rec-num">{String(i + 1).padStart(2, "0")}</span>
                <div className="wrep-rec-body">
                  <div className="wrep-rec-header">
                    <span className="wrep-priority-chip" style={{ color: p.color, background: p.bg }}>
                      {p.label}
                    </span>
                    <span className="wrep-rec-action">{rec.action}</span>
                  </div>
                  {rec.reason && <p className="wrep-rec-reason">{rec.reason}</p>}
                  {rec.expected_impact && (
                    <span className="wrep-rec-impact">
                      <TrendingUp size={10} />
                      {rec.expected_impact}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function nextMondayLabel(): string {
  const nextMon = addDays(startOfWeek(new Date(), { weekStartsOn: 1 }), 7);
  return format(nextMon, "EEEE, d MMMM", { locale: id });
}

export function WeeklyInsightReport({ channelId }: Props) {
  const { data: report, isLoading } = useWeeklyReport(channelId);

  if (isLoading) {
    return (
      <div className="wrep-panel">
        <div className="wrep-header-band">
          <div className="skeleton" style={{ width: 80, height: 14, borderRadius: 4 }} />
          <div className="skeleton" style={{ width: 200, height: 22, borderRadius: 4, marginTop: 6 }} />
        </div>
        <div style={{ padding: "16px 24px", display: "flex", flexDirection: "column", gap: 10 }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 48, borderRadius: 8 }} />
          ))}
        </div>
      </div>
    );
  }

  if (!report || !report.available) {
    return (
      <div className="wrep-panel">
        <div className="wrep-header-band">
          <span className="wrep-ai-label"><Zap size={10} /> AI REPORT</span>
          <h3 className="wrep-title">Laporan Mingguan</h3>
        </div>
        <div className="analytics-retention-empty" style={{ padding: "40px 24px" }}>
          <Clock size={32} strokeWidth={1.5} />
          <p>Laporan pertama akan dibuat hari Senin</p>
          <p className="muted" style={{ fontSize: 12 }}>
            {report?.message ?? "AI akan menganalisis performa channel dan memberikan rekomendasi aksi."}
          </p>
        </div>
      </div>
    );
  }

  const weekLabel = report.week_start && report.week_end
    ? format(parseISO(report.week_start), "d MMM", { locale: id }) +
      " – " +
      format(parseISO(report.week_end), "d MMM yyyy", { locale: id })
    : "";

  const viewsChange    = report.views_change_pct;
  const subsChange     = report.subscribers_change;
  const showStats      = viewsChange != null || (subsChange != null && subsChange !== -1);
  const hasTopClipType = report.top_clip_type &&
    !report.top_clip_type.toLowerCase().startsWith("tidak ada") &&
    report.top_clip_type.length <= 40;

  return (
    <div className="wrep-panel">
      {/* ── Header Band ── */}
      <div className="wrep-header-band">
        <div className="wrep-header-row">
          <div className="wrep-header-left">
            <span className="wrep-ai-label"><Zap size={10} /> AI REPORT</span>
            <h3 className="wrep-title">Laporan Mingguan</h3>
            {weekLabel && <span className="wrep-date-label">{weekLabel}</span>}
          </div>
          <span className="wrep-badge-done">
            <CheckCircle size={11} /> Selesai
          </span>
        </div>

        {/* Executive Summary */}
        {report.summary && (
          <div className="wrep-summary-block">
            <span className="wrep-summary-accent" />
            <p className="wrep-summary-text">
              <span className="wrep-summary-bold">TL;DR</span>{" "}
              {report.summary}
            </p>
          </div>
        )}
      </div>

      {/* ── Metrics Strip ── */}
      {showStats && (
        <div className="wrep-metrics-strip">
          {viewsChange != null && (
            <div className="wrep-metric">
              <span
                className="wrep-metric-val"
                style={{ color: viewsChange >= 0 ? "#00D4AA" : "#FF6B6B" }}
              >
                {viewsChange >= 0 ? "+" : ""}{viewsChange.toFixed(1)}%
              </span>
              <span className="wrep-metric-lbl">Views vs minggu lalu</span>
            </div>
          )}
          {subsChange != null && subsChange !== -1 && (
            <div className="wrep-metric">
              <span
                className="wrep-metric-val"
                style={{ color: subsChange >= 0 ? "#00D4AA" : "#FF6B6B" }}
              >
                {subsChange >= 0 ? "+" : ""}{subsChange}
              </span>
              <span className="wrep-metric-lbl">Subscribers</span>
            </div>
          )}
          {hasTopClipType && (
            <div className="wrep-metric">
              <span className="wrep-metric-val" style={{ fontSize: 14 }}>
                {report.top_clip_type}
              </span>
              <span className="wrep-metric-lbl">Top clip type</span>
            </div>
          )}
        </div>
      )}

      {/* ── Content Sections ── */}
      <div className="wrep-sections">
        <Section
          icon={<TrendingUp size={13} />}
          title="Wins Minggu Ini"
          items={report.wins ?? []}
          accentColor="#00D4AA"
          accentBg="rgba(0,212,170,0.1)"
        />
        <Section
          icon={<AlertCircle size={13} />}
          title="Perlu Perhatian"
          items={report.issues ?? []}
          accentColor="#FF6B6B"
          accentBg="rgba(255,107,107,0.1)"
        />
        <RecsSection recs={report.recommendations ?? []} />
      </div>

      {/* ── Footer ── */}
      <div className="wrep-footer">
        <div className="wrep-next-label">
          <Clock size={11} />
          <span>Laporan berikutnya: <strong>{nextMondayLabel()}</strong></span>
        </div>
        <div className="wrep-footer-btns">
          <button className="wrep-btn">
            <Bell size={12} /> Kirim ke Telegram
          </button>
          <button className="wrep-btn wrep-btn-accent">
            <FileDown size={12} /> Export PDF
          </button>
        </div>
      </div>
    </div>
  );
}
