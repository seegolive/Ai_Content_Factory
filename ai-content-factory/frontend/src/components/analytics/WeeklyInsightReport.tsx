"use client";
import { FileText, TrendingUp, AlertCircle, Lightbulb, CheckCircle, Bell, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { useWeeklyReport } from "@/hooks/useAnalytics";
import { format, parseISO, addDays, startOfWeek } from "date-fns";
import { id } from "date-fns/locale";
import type { WeeklyInsightReport as ReportType } from "@/types/analytics";

interface Props {
  channelId: string | null;
}

function Section({
  icon,
  title,
  items,
  color,
}: {
  icon: React.ReactNode;
  title: string;
  items: string[];
  color: string;
}) {
  const [open, setOpen] = useState(true);
  if (!items?.length) return null;
  return (
    <div className="weekly-section">
      <button className="weekly-section-header" onClick={() => setOpen((o) => !o)}>
        <span style={{ color }}>{icon}</span>
        <span className="weekly-section-title" style={{ color }}>
          {title}
        </span>
        <span className="weekly-section-count">{items.length}</span>
        <span className="weekly-section-chevron">
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </span>
      </button>
      {open && (
        <ul className="weekly-section-items">
          {items.map((item, i) => (
            <li key={i} className="weekly-item">
              <span className="weekly-item-bullet" style={{ background: color }} />
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RecsSection({ recs }: { recs: NonNullable<ReportType["recommendations"]> }) {
  const [open, setOpen] = useState(true);
  if (!recs?.length) return null;
  const priorityColor: Record<string, string> = {
    high: "#FF6B6B",
    medium: "#F0B429",
    low: "#6B6B8A",
  };
  return (
    <div className="weekly-section">
      <button className="weekly-section-header" onClick={() => setOpen((o) => !o)}>
        <span style={{ color: "#6C63FF" }}><Lightbulb size={14} /></span>
        <span className="weekly-section-title" style={{ color: "#6C63FF" }}>
          Rekomendasi Aksi
        </span>
        <span className="weekly-section-count">{recs.length}</span>
        <span className="weekly-section-chevron">
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </span>
      </button>
      {open && (
        <ul className="weekly-section-items">
          {recs.map((rec, i) => (
            <li key={i} className="weekly-item weekly-rec-item">
              <span
                className="weekly-item-bullet"
                style={{ background: priorityColor[rec.priority] ?? "#6C63FF" }}
              />
              <div>
                <div style={{ fontWeight: 600, color: "#E8E8F0" }}>{rec.action}</div>
                <div className="muted" style={{ fontSize: 12 }}>
                  {rec.reason}
                  {rec.expected_impact && (
                    <> · <span style={{ color: "#00D4AA" }}>{rec.expected_impact}</span></>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
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
      <div className="panel">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="skeleton" style={{ height: 56, borderRadius: 6, marginBottom: 8 }} />
        ))}
      </div>
    );
  }

  if (!report || !report.available) {
    return (
      <div className="panel analytics-chart-panel">
        <div className="analytics-chart-header">
          <h3 className="analytics-section-title">
            <FileText size={16} /> Laporan Mingguan AI
          </h3>
        </div>
        <div className="analytics-retention-empty">
          <FileText size={32} strokeWidth={1.5} />
          <p>Laporan pertama akan dibuat hari Senin</p>
          <p className="muted">
            {report?.message ?? "AI akan menganalisis performa channel minggu ini dan memberikan rekomendasi aksi."}
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

  const viewsChange = report.views_change_pct;
  const subsChange = report.subscribers_change;

  return (
    <div className="panel analytics-chart-panel weekly-report-panel">
      <div className="analytics-chart-header">
        <div>
          <h3 className="analytics-section-title">
            <FileText size={16} /> Laporan Mingguan AI
          </h3>
          {weekLabel && <p className="muted" style={{ fontSize: 12, marginTop: 2 }}>{weekLabel}</p>}
        </div>
        <span className="status-badge generated">Selesai</span>
      </div>

      {/* TL;DR / Summary */}
      {report.summary && (
        <div className="weekly-tldr">
          <strong>TL;DR:</strong> {report.summary}
        </div>
      )}

      {/* Quick stats row */}
      <div className="weekly-stats-row">
        {viewsChange != null && (
          <div className="weekly-stat">
            <span
              className="weekly-stat-value"
              style={{ color: viewsChange >= 0 ? "#00D4AA" : "#FF6B6B" }}
            >
              {viewsChange >= 0 ? "+" : ""}{viewsChange.toFixed(1)}%
            </span>
            <span className="weekly-stat-label">Views vs minggu lalu</span>
          </div>
        )}
        {subsChange != null && (
          <div className="weekly-stat">
            <span
              className="weekly-stat-value"
              style={{ color: subsChange >= 0 ? "#00D4AA" : "#FF6B6B" }}
            >
              {subsChange >= 0 ? "+" : ""}{subsChange}
            </span>
            <span className="weekly-stat-label">Subscribers</span>
          </div>
        )}
        {report.top_clip_type && (
          <div className="weekly-stat">
            <span className="weekly-stat-value">{report.top_clip_type}</span>
            <span className="weekly-stat-label">Top clip type</span>
          </div>
        )}
      </div>

      <Section
        icon={<TrendingUp size={14} />}
        title="Wins Minggu Ini"
        items={report.wins ?? []}
        color="#00D4AA"
      />
      <Section
        icon={<AlertCircle size={14} />}
        title="Perlu Perhatian"
        items={report.issues ?? []}
        color="#FF6B6B"
      />
      <RecsSection recs={report.recommendations ?? []} />

      {/* Footer */}
      <div className="weekly-footer">
        <div className="weekly-next-report">
          <CheckCircle size={12} />
          Laporan berikutnya:{" "}
          <strong>{nextMondayLabel()}</strong>
        </div>
        <div className="weekly-actions">
          <button className="btn-ghost-sm">
            <Bell size={12} /> Kirim ke Telegram
          </button>
          <button className="btn-ghost-sm">
            Export PDF
          </button>
        </div>
      </div>
    </div>
  );
}
