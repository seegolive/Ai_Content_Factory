"use client";

import { useRouter } from "next/navigation";
import { useState, useEffect, useRef, useMemo } from "react";
import {
  Video, Scissors, CheckCircle, Upload, ArrowRight, Zap, RefreshCw,
  Youtube, Eye, BarChart2, AlertCircle, ChevronRight, Flame, PlayCircle,
} from "lucide-react";
import { Header } from "@/components/layout/Header";
import { VideoUploader } from "@/components/video/VideoUploader";
import { useVideos, useYoutubeStats, useClipStats, useVideoStatus, useAnalyticsDailyStats } from "@/lib/queries";
import { formatRelativeTime, formatDuration } from "@/lib/utils";

/* ─── Animated Counter ──────────────────────────────────── */
function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);
  const displayRef = useRef(0);
  const raf = useRef<number | null>(null);
  useEffect(() => {
    const start = displayRef.current;
    if (start === value) return;
    const t0 = performance.now();
    const step = (now: number) => {
      const p = Math.min((now - t0) / 800, 1);
      const e = 1 - Math.pow(1 - p, 3);
      const current = Math.round(start + (value - start) * e);
      displayRef.current = current;
      setDisplay(current);
      if (p < 1) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); };
  }, [value]);
  return <>{display}</>;
}

/* ─── Sparkline ─────────────────────────────────────────── */
function Sparkline({ data, color }: { data: number[]; color: string }) {
  const W = 100, H = 28;
  const padded = [...Array(Math.max(0, 7 - data.length)).fill(0), ...data.slice(-7)];
  const max = Math.max(...padded, 1);
  const min = Math.min(...padded);
  const range = max - min || 1;
  const pts = padded.map((v, i) => {
    const x = (i / (padded.length - 1)) * W;
    const y = H - ((v - min) / range) * (H - 4) - 2;
    return `${x},${y}`;
  }).join(" ");
  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5}
        strokeLinejoin="round" strokeLinecap="round" opacity={0.7} />
    </svg>
  );
}

/* ─── Skeleton Block ─────────────────────────────────────── */
function Skel({ w, h, radius = 6 }: { w: number | string; h: number; radius?: number }) {
  return <div className="skeleton" style={{ width: w, height: h, borderRadius: radius, flexShrink: 0 }} />;
}

/* ─── Status Badge ───────────────────────────────────────── */
const STATUS_CFG: Record<string, { bg: string; color: string; label: string }> = {
  review:     { bg: "rgba(245,158,11,.1)",   color: "var(--warning)",      label: "Review" },
  published:  { bg: "rgba(0,212,170,.1)",    color: "var(--secondary)",    label: "Published" },
  processing: { bg: "rgba(124,111,255,.1)",  color: "var(--primary-text)", label: "Processing" },
  queued:     { bg: "rgba(255,255,255,.04)", color: "var(--text-3)",       label: "Queued" },
  done:       { bg: "rgba(0,212,170,.1)",    color: "var(--secondary)",    label: "Done" },
  error:      { bg: "rgba(248,113,113,.1)",  color: "var(--danger)",       label: "Error" },
};
function StatusBadge({ status }: { status: string }) {
  const c = STATUS_CFG[status] ?? STATUS_CFG.queued;
  return (
    <span className="db-status-badge" style={{ background: c.bg, color: c.color, borderColor: `${c.color}50` }}>
      {c.label}
    </span>
  );
}

/* ─── Tag Pill ───────────────────────────────────────────── */
const TAG_CFG: Record<string, { color: string; bg: string; border: string }> = {
  clutch:   { color: "#a78bfa", bg: "rgba(167,139,250,.08)", border: "rgba(167,139,250,.3)" },
  funny:    { color: "#ffb347", bg: "rgba(255,179,71,.08)",  border: "rgba(255,179,71,.3)" },
  fail:     { color: "#4d9fff", bg: "rgba(77,159,255,.08)",  border: "rgba(77,159,255,.3)" },
  rage:     { color: "#ff4d6d", bg: "rgba(255,77,109,.08)",  border: "rgba(255,77,109,.3)" },
  flagged:  { color: "var(--warning)", bg: "rgba(245,158,11,.08)", border: "rgba(245,158,11,.3)" },
};
function TagPill({ type }: { type: string }) {
  const c = TAG_CFG[type] ?? TAG_CFG.fail;
  return (
    <span className="db-tag-pill" style={{ color: c.color, background: c.bg, borderColor: c.border }}>
      {type}
    </span>
  );
}

/* ─── Card Shell ─────────────────────────────────────────── */
function Card({ className = "", style = {}, onClick, children }: {
  className?: string; style?: React.CSSProperties; onClick?: () => void; children: React.ReactNode;
}) {
  return <div className={`db-card ${className}`} style={style} onClick={onClick}>{children}</div>;
}

/* ─── Card Header ────────────────────────────────────────── */
function CardHeader({ icon, title, badge, action }: {
  icon?: React.ReactNode; title: string; badge?: React.ReactNode; action?: React.ReactNode;
}) {
  return (
    <div className="db-card-hd">
      <div className="db-card-hd-left">
        {icon && <div className="db-card-icon">{icon}</div>}
        <span className="db-card-title">{title}</span>
        {badge}
      </div>
      {action}
    </div>
  );
}

/* ─── Performance Chart (SVG) ────────────────────────────── */
function PerformanceChart({ views, clips }: { views: number[]; clips: number[] }) {
  const W = 400, H = 150;
  const PAD = { t: 8, r: 8, b: 8, l: 8 };
  const iW = W - PAD.l - PAD.r, iH = H - PAD.t - PAD.b;
  const maxV = Math.max(...views, ...clips, 1);
  const toPath = (arr: number[]) => arr.map((v, i) => {
    const x = PAD.l + (i / Math.max(arr.length - 1, 1)) * iW;
    const y = PAD.t + iH - (v / maxV) * iH;
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const vp = toPath(views), cp = toPath(clips);
  const gridYs = [0.25, 0.5, 0.75].map(p => PAD.t + iH - p * iH);
  const lx = (PAD.l + iW).toFixed(1);
  const vly = views.length > 1 ? (PAD.t + iH - (views[views.length - 1] / maxV) * iH).toFixed(1) : null;
  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ display: "block" }}>
      {gridYs.map((y, i) => (
        <line key={i} x1={PAD.l} y1={y} x2={W - PAD.r} y2={y}
          stroke="rgba(255,255,255,0.05)" strokeWidth={1} strokeDasharray="4 4" />
      ))}
      <path d={`${vp} L${W - PAD.r},${PAD.t + iH} L${PAD.l},${PAD.t + iH} Z`} fill="rgba(124,111,255,.06)" />
      <path d={`${cp} L${W - PAD.r},${PAD.t + iH} L${PAD.l},${PAD.t + iH} Z`} fill="rgba(0,212,170,.06)" />
      <path d={vp} fill="none" stroke="var(--primary-text)" strokeWidth={2} strokeLinejoin="round" />
      <path d={cp} fill="none" stroke="var(--secondary)" strokeWidth={2} strokeLinejoin="round" strokeDasharray="5 3" />
      {vly && (
        <>
          <circle cx={lx} cy={vly} r={5} fill="var(--primary)" opacity={0.3} />
          <circle cx={lx} cy={vly} r={3} fill="var(--primary-text)" />
        </>
      )}
    </svg>
  );
}

/* ─── Pipeline constants ─────────────────────────────────── */
const PIPELINE_STAGES = [
  { key: "upload",     label: "Upload" },
  { key: "transcribe", label: "Transcribe" },
  { key: "analyze",    label: "Analyze" },
  { key: "review",     label: "Review" },
  { key: "publish",    label: "Publish" },
];
// Maps last-completed checkpoint → which pipeline stage is NOW ACTIVE
// input_validated = validation done → Transcribe is now running
// transcript_done = transcription done → Analyze is now running
// ai_done/qc_done = analysis done → cutting clips (still Analyze visually)
// clips_done/review_ready = clips ready → Review stage
const CHECKPOINT_IDX: Record<string, number> = {
  downloading:     0,  // Upload stage active
  input_validated: 1,  // Transcribe stage active (transcription starting)
  transcribing:    1,  // Transcribe stage active (Whisper running)
  transcript_done: 2,  // Analyze stage active
  ai_done:         2,  // still Analyze (QC running)
  qc_done:         3,  // Review stage (clips being cut)
  clips_done:      3,  // Review stage (waiting review)
  review_ready:    3,  // Review stage ready
};

// Human-readable label for what the pipeline is CURRENTLY doing
const CHECKPOINT_DOING: Record<string, string> = {
  downloading:     "Downloading",
  input_validated: "Transcribing",
  transcribing:    "Transcribing",
  transcript_done: "AI Scoring",
  ai_done:         "Quality Check",
  qc_done:         "Cutting Clips",
  clips_done:      "Ready for Review",
  review_ready:    "Ready for Review",
};

const ADOT: Record<string, { border: string; bg: string; color: string }> = {
  success: { border: "rgba(0,212,170,.4)",   bg: "rgba(0,212,170,.08)",   color: "var(--secondary)" },
  info:    { border: "rgba(124,111,255,.4)", bg: "rgba(124,111,255,.08)", color: "var(--primary-text)" },
  warn:    { border: "rgba(245,158,11,.4)",  bg: "rgba(245,158,11,.08)",  color: "var(--warning)" },
  error:   { border: "rgba(248,113,113,.4)", bg: "rgba(248,113,113,.08)", color: "var(--danger)" },
};

/* ─── Helpers ────────────────────────────────────────────── */
function fmtNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return `${n}`;
}

/* ═══════════════════════════════════════════════════════════
   DASHBOARD PAGE
   ═══════════════════════════════════════════════════════════ */
export default function DashboardPage() {
  const router = useRouter();
  const [showUploader, setShowUploader] = useState(false);
  const [chartRange, setChartRange] = useState<"7d" | "30d" | "90d">("7d");
  const chartDays = chartRange === "7d" ? 7 : chartRange === "30d" ? 30 : 90;

  const { data: allVideos = [], isLoading } = useVideos();
  const { data: reviewVideos = [] }         = useVideos({ status: "review" });
  const { data: processingVideos = [] }     = useVideos({ status: "processing" });
  const { data: ytData, isLoading: ytLoading } = useYoutubeStats();
  const { data: clipStats }                 = useClipStats();
  const ytChannelId = ytData?.accounts?.[0]?.channel_id;
  const { data: dailyStats }               = useAnalyticsDailyStats(ytChannelId, chartDays);

  const totalVideos = allVideos.length;
  const totalClips  = clipStats?.total     ?? 0;
  const pending     = clipStats?.pending   ?? 0;
  const published   = clipStats?.published ?? 0;
  const approved    = clipStats?.approved  ?? 0;

  const [greeting, setGreeting] = useState("Good evening");
  useEffect(() => {
    const h = new Date().getHours();
    setGreeting(h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening");
  }, []);

  const ytAccount = ytData?.accounts?.[0];

  // Real sparkline: per-day upload count from allVideos.created_at
  const sparkVideos = useMemo(() => {
    const today = new Date();
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(today);
      d.setDate(d.getDate() - (6 - i));
      const dateStr = d.toISOString().slice(0, 10);
      return allVideos.filter(v => v.created_at.slice(0, 10) === dateStr).length;
    });
  }, [allVideos]);
  // Flat zeros for metrics without time-series data (no fake trend)
  const sparkClips     = useMemo(() => Array(7).fill(0) as number[], []);
  const sparkPublished = useMemo(() => Array(7).fill(0) as number[], []);
  const sparkApproved  = useMemo(() => Array(7).fill(0) as number[], []);

  // Real performance data: views from analytics daily-stats, clips per day from allVideos
  const perfViews = dailyStats?.views ?? [];
  const perfClips = useMemo(() => {
    const today = new Date();
    return Array.from({ length: chartDays }, (_, i) => {
      const d = new Date(today);
      d.setDate(d.getDate() - (chartDays - 1 - i));
      const dateStr = d.toISOString().slice(0, 10);
      return allVideos
        .filter(v => v.created_at.slice(0, 10) === dateStr)
        .reduce((sum, v) => sum + (v.clips_count || 0), 0);
    });
  }, [allVideos, chartDays]);
  const perfViewsTotal = perfViews.reduce((a, b) => a + b, 0);
  const perfWatchTime  = dailyStats
    ? Math.round(dailyStats.watch_time_minutes.reduce((a, b) => a + b, 0) / 60)
    : 0;

  // Real AI activity derived from pipeline video events
  type ActivityType = "success" | "info" | "warn" | "error";
  interface ActivityEntry {
    id: string;
    type: ActivityType;
    title: React.ReactNode;
    time: string;
    source: string;
  }
  const activityItems = useMemo((): ActivityEntry[] => {
    const sorted = [...allVideos].sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    );
    const items: ActivityEntry[] = [];
    for (const v of sorted.slice(0, 6)) {
      // Clean display name: if title is still a raw URL, show short placeholder
      const rawTitle = v.title ?? "";
      const isUrl = rawTitle.startsWith("http");
      const name = isUrl ? "video" : (rawTitle || "Untitled");
      const relTime = formatRelativeTime(v.updated_at);
      if (v.copyright_status === "flagged") {
        items.push({
          id: `${v.id}-cr`,
          type: "warn",
          title: (<>Copyright flag on <strong style={{ color: "var(--warning)" }}>{name}</strong></>),
          time: relTime,
          source: "ACRCloud",
        });
      }
      if (v.status === "done" && v.clips_count > 0) {
        items.push({
          id: v.id,
          type: "success",
          title: (<>Generated <strong style={{ color: "var(--secondary)" }}>{v.clips_count} clip{v.clips_count !== 1 ? "s" : ""}</strong> from {name}</>),
          time: relTime,
          source: "Pipeline",
        });
      } else if (v.status === "processing") {
        const checkpoint = v.checkpoint;
        const dlPct = v.download_progress ?? 0;
        const stageLabel = !checkpoint && dlPct > 0
          ? `downloading ${dlPct}%`
          : CHECKPOINT_DOING[checkpoint ?? ""] ?? (checkpoint ?? "processing").replace(/_/g, " ");
        const pctSuffix = checkpoint === "input_validated" && dlPct > 0 ? ` ${dlPct}%` : "";
        items.push({
          id: v.id,
          type: "info",
          title: (<>Processing <strong style={{ color: "#4d9fff" }}>{isUrl ? "new video" : name}</strong> — {stageLabel}{pctSuffix}</>),
          time: relTime,
          source: "Pipeline",
        });
      } else if (v.status === "error") {
        items.push({
          id: v.id,
          type: "error",
          title: (<>Pipeline failed — <strong style={{ color: "var(--danger)" }}>{name}</strong></>),
          time: relTime,
          source: "Pipeline",
        });
      } else if (v.status === "review") {
        items.push({
          id: v.id,
          type: "info",
          title: (<>{v.clips_count} clip{v.clips_count !== 1 ? "s" : ""} ready to review from <strong style={{ color: "#4d9fff" }}>{name}</strong></>),
          time: relTime,
          source: "Pipeline",
        });
      }
    }
    return items.slice(0, 4);
  }, [allVideos]);

  const latestProcId = processingVideos[0]?.id ?? "";
  const { data: pipelineStatus } = useVideoStatus(latestProcId, !!latestProcId);
  const activeStageIdx = useMemo(
    () => (pipelineStatus ? (CHECKPOINT_IDX[pipelineStatus.current_stage ?? ""] ?? -1) : -1),
    [pipelineStatus]
  );
  const pipelineActive = processingVideos.length > 0;
  // Use backend progress_percent (which now factors in download_progress for stage 0)
  // Fall back to a non-zero minimum so the bar is visible when pipeline is active
  const pipelineProgress = useMemo(() => {
    if (!pipelineStatus) return pipelineActive ? 2 : 0;
    if (pipelineStatus.progress_percent > 0) return pipelineStatus.progress_percent;
    // Backend gave 0 — use download_progress scaled to first 15% of pipeline
    const dl = pipelineStatus.download_progress ?? 0;
    return dl > 0 ? Math.max(1, Math.round(dl * 0.15)) : (pipelineActive ? 2 : 0);
  }, [pipelineStatus, pipelineActive]);

  return (
    <>
      <Header
        breadcrumb={[{ label: "Dashboard" }]}
        actions={
          <button className="btn-primary" onClick={() => setShowUploader(true)}>
            <Upload size={13} /> Upload Video
          </button>
        }
      />

      <div className="page-scroll">
        <div className="db-page">

          {/* ── Hero Strip ─────────────────────────────── */}
          <div className="db-hero anim-0">
            <div className="db-hero-bg" />
            <div className="db-hero-text">
              <div className="db-hero-eyebrow">
                {greeting} ·{" "}
                {new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
              </div>
              <h1 className="db-hero-title">
                {pending > 0 ? (
                  <>Hi Creator, <strong>{pending > 99 ? "99+" : pending} clips</strong> waiting for review</>
                ) : (
                  <>Hi Creator, <strong>all clips are reviewed!</strong> 🎉</>
                )}
              </h1>
              <p className="db-hero-sub">
                {pending > 0
                  ? "Review and publish your top clips to grow your channel faster."
                  : "Upload a new video to start generating fresh clips with AI."}
              </p>
            </div>
            <div className="db-hero-actions">
              <button className="db-btn-secondary" onClick={() => router.push("/settings")}>
                <RefreshCw size={13} /> Sync Channel
              </button>
              {pending > 0 ? (
                <button className="db-btn-primary" onClick={() => router.push("/review")}>
                  Review Now <ArrowRight size={14} />
                </button>
              ) : (
                <button className="db-btn-primary" onClick={() => setShowUploader(true)}>
                  <Upload size={13} /> Upload Video
                </button>
              )}
            </div>
          </div>

          {/* ── Bento Grid ─────────────────────────────── */}
          <div className="db-bento">

            {/* 1. Primary KPI — Pending Review (4×2) */}
            <Card className="db-kpi-primary" style={{ animationDelay: "60ms" }} onClick={() => router.push("/review")}>
              <div className="db-kpi-primary-glow" />
              <CardHeader
                icon={<Eye size={13} style={{ color: "var(--warning)" }} />}
                title="Pending Review"
              />
              <div className="db-kpi-primary-value">
                {isLoading ? <Skel w={80} h={64} radius={8} /> : <AnimatedNumber value={Math.min(pending, 99)} />}
                {pending > 99 && <span style={{ fontSize: 40 }}>+</span>}
              </div>
              <div className="db-kpi-primary-label">clips ready to review &amp; publish</div>
              <button className="db-kpi-primary-cta" onClick={e => { e.stopPropagation(); router.push("/review"); }}>
                Review now <ArrowRight size={12} />
              </button>
              <div className="db-kpi-primary-meta">
                {reviewVideos.length > 0 && `${reviewVideos.length} video${reviewVideos.length !== 1 ? "s" : ""} in queue`}
              </div>
            </Card>

            {/* 2. Connected Channel (4×2) */}
            <Card className="db-channel-card" style={{ animationDelay: "100ms" }}>
              <CardHeader
                icon={<Youtube size={13} style={{ color: "var(--danger)" }} />}
                title="Channel"
                action={
                  <button className="db-card-link" onClick={() => router.push("/settings")}>
                    Manage <ChevronRight size={11} />
                  </button>
                }
              />
              {isLoading || ytLoading ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 12, paddingTop: 4 }}>
                  <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                    <Skel w={44} h={44} radius={22} />
                    <div><Skel w={130} h={14} /><div style={{ marginTop: 5 }}><Skel w={90} h={11} /></div></div>
                  </div>
                  <Skel w="100%" h={60} radius={8} />
                </div>
              ) : ytAccount ? (
                <>
                  <div className="db-channel-info">
                    <div className="db-channel-avatar">
                      {ytAccount.thumbnail_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={ytAccount.thumbnail_url} alt={ytAccount.channel_name ?? "channel"} style={{ width: 44, height: 44, borderRadius: "50%", objectFit: "cover" }} />
                      ) : (
                        ytAccount.channel_name?.charAt(0).toUpperCase() ?? "Y"
                      )}
                    </div>
                    <div>
                      <div className="db-channel-name">{ytAccount.channel_name ?? ytAccount.channel_id}</div>
                      <div className="db-channel-handle">{ytAccount.channel_id}</div>
                      <div className="db-channel-badge"><Youtube size={9} /> YouTube</div>
                    </div>
                  </div>
                  <div className="db-channel-stats">
                    <div>
                      <div className="db-channel-stat-val">
                        {ytAccount.subscriber_count != null ? fmtNum(ytAccount.subscriber_count) : "—"}
                      </div>
                      <div className="db-channel-stat-key">Subscribers</div>
                    </div>
                    <div>
                      <div className="db-channel-stat-val">
                        {ytAccount.video_count != null ? fmtNum(ytAccount.video_count) : "—"}
                      </div>
                      <div className="db-channel-stat-key">YT Videos</div>
                    </div>
                    <div>
                      <div className="db-channel-stat-val" style={{ color: "var(--secondary)" }}>
                        {ytAccount.total_views != null ? fmtNum(ytAccount.total_views) : "—"}
                      </div>
                      <div className="db-channel-stat-key">Total Views</div>
                    </div>
                  </div>
                  {ytAccount.error && (
                    <div style={{ fontSize: 10, color: "var(--danger)", marginTop: 6, opacity: 0.8 }}>
                      ⚠ {ytAccount.error}
                    </div>
                  )}
                </>
              ) : (
                <div className="db-channel-empty">
                  <Youtube size={28} style={{ color: "var(--danger)", opacity: 0.45, marginBottom: 10 }} />
                  <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-2)", marginBottom: 4 }}>No channel connected</div>
                  <div style={{ fontSize: 11, color: "var(--text-4)", marginBottom: 12 }}>Connect YouTube to enable publishing</div>
                  <button className="db-btn-primary" style={{ height: 30, fontSize: 11, padding: "0 12px" }} onClick={() => router.push("/settings")}>
                    Connect Channel
                  </button>
                </div>
              )}
            </Card>

            {/* 3–6. Secondary KPIs (each 2×1) */}
            {([
              { label: "Videos",    value: totalVideos, sublabel: "total uploaded",  trend: 1, accent: "var(--primary-text)", spark: sparkVideos },
              { label: "Clips",     value: totalClips,  sublabel: "generated total", trend: 6, accent: "var(--secondary)",   spark: sparkClips },
              { label: "Approved",  value: approved,    sublabel: "clips approved",  trend: 5, accent: "#00e5a0",            spark: sparkApproved },
              { label: "Published", value: published,   sublabel: "clips published", trend: 3, accent: "var(--danger)",      spark: sparkPublished },
            ] as const).map(({ label, value, sublabel, trend, accent, spark }, i) => (
              <Card key={label} className="db-kpi-card" style={{ animationDelay: `${140 + i * 40}ms` }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                  <span className="db-kpi-section-label">{label}</span>
                  {value > 0 && (
                    <span className="db-kpi-trend" style={{ color: "var(--secondary)" }}>
                      ↑ +{trend}
                    </span>
                  )}
                </div>
                {isLoading ? (
                  <>
                    <div style={{ marginTop: 6 }}><Skel w={80} h={28} radius={6} /></div>
                    <div style={{ marginTop: 4 }}><Skel w={100} h={10} radius={4} /></div>
                  </>
                ) : (
                  <>
                    <div className="db-kpi-value" style={{ color: accent }}><AnimatedNumber value={value} /></div>
                    <div className="db-kpi-sublabel">{sublabel}</div>
                  </>
                )}
                <div className="db-kpi-sparkline"><Sparkline data={spark} color={accent} /></div>
              </Card>
            ))}

            {/* 7. Recent Videos (7×3) */}
            <Card className="db-recent-videos" style={{ animationDelay: "300ms" }}>
              <CardHeader
                icon={<Video size={13} style={{ color: "var(--text-3)" }} />}
                title="Recent Videos"
                badge={!isLoading && <span className="db-count-badge">{allVideos.length} total</span>}
                action={<button className="db-card-link" onClick={() => router.push("/videos")}>All videos <ArrowRight size={11} /></button>}
              />
              <div className="db-video-list">
                {isLoading ? (
                  Array.from({ length: 5 }, (_, i) => (
                    <div key={i} className="db-video-item" style={{ cursor: "default" }}>
                      <Skel w={90} h={50} radius={6} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <Skel w="65%" h={13} /><div style={{ marginTop: 5 }}><Skel w="35%" h={10} /></div>
                      </div>
                      <Skel w={72} h={22} radius={4} />
                    </div>
                  ))
                ) : allVideos.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-icon"><Upload size={20} style={{ color: "var(--primary-text)" }} /></div>
                    <div className="empty-title">No videos yet</div>
                    <div className="empty-desc">Upload your first video to start the AI pipeline.</div>
                    <button className="btn-primary" onClick={() => setShowUploader(true)}><Upload size={13} /> Upload Video</button>
                  </div>
                ) : allVideos.slice(0, 5).map(v => (
                  <div key={v.id} className="db-video-item" onClick={() => router.push(`/videos/${v.id}`)}>
                    <div className="db-video-thumb">
                      <span style={{ fontSize: 20 }}>🎮</span>
                      <div className="db-video-dur">
                        {v.duration_seconds != null
                          ? `${Math.floor(v.duration_seconds / 60)}:${String(v.duration_seconds % 60).padStart(2, "0")}`
                          : "--"}
                      </div>
                    </div>
                    <div className="db-video-info">
                      <div className="db-video-title">{v.title ?? "Untitled Video"}</div>
                      <div className="db-video-meta">
                        <span>{formatRelativeTime(v.created_at)}</span>
                        {v.clips_count > 0 && <span style={{ color: "var(--secondary)" }}>{v.clips_count} clips</span>}
                      </div>
                    </div>
                    <StatusBadge status={v.status} />
                  </div>
                ))}
              </div>
            </Card>

            {/* 8. Review Queue (5×3) */}
            <Card className="db-review-queue" style={{ animationDelay: "340ms" }}>
              <CardHeader
                icon={<Flame size={13} style={{ color: "var(--warning)" }} />}
                title="Review Queue"
                badge={reviewVideos.length > 0 && <span className="db-amber-badge">{reviewVideos.length}</span>}
                action={reviewVideos.length > 0 ? <button className="db-card-link" onClick={() => router.push("/review")}>Review all <ArrowRight size={11} /></button> : undefined}
              />
              <div className="db-queue-list">
                {isLoading ? (
                  Array.from({ length: 4 }, (_, i) => (
                    <div key={i} className="db-queue-item" style={{ cursor: "default" }}>
                      <Skel w={70} h={40} radius={5} />
                      <div style={{ flex: 1, minWidth: 0 }}><Skel w="80%" h={12} /><div style={{ marginTop: 4 }}><Skel w="40%" h={10} /></div></div>
                    </div>
                  ))
                ) : reviewVideos.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-icon" style={{ background: "var(--secondary-dim)", borderColor: "rgba(0,212,170,.2)" }}>
                      <CheckCircle size={20} style={{ color: "var(--secondary)" }} />
                    </div>
                    <div className="empty-title">Queue is clear 🎉</div>
                    <div className="empty-desc">All clips have been reviewed.</div>
                  </div>
                ) : reviewVideos.slice(0, 6).map((v) => {
                  const clipsColor = v.clips_count > 5
                    ? "var(--secondary)"
                    : v.clips_count > 0 ? "var(--warning)" : "rgba(255,255,255,.25)";
                  return (
                    <div key={v.id} className="db-queue-item" onClick={() => router.push(`/videos/${v.id}`)}>
                      <div className="db-queue-thumb">
                        <span style={{ fontSize: 16 }}>🎮</span>
                        <div className="db-queue-score" style={{ color: clipsColor, boxShadow: `inset 0 0 0 2px ${clipsColor}` }}>{v.clips_count}</div>
                      </div>
                      <div className="db-queue-info">
                        <div className="db-queue-title">{v.title ?? "Untitled"}</div>
                        <div className="db-queue-meta">
                          {v.copyright_status === "flagged"
                            ? <TagPill type="flagged" />
                            : <StatusBadge status={v.status} />}
                          <span className="db-queue-dur">{formatDuration(v.duration_seconds)}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* 9. Performance Trend (4×2) */}
            <Card className="db-chart-card" style={{ animationDelay: "380ms" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div className="db-card-icon"><BarChart2 size={13} style={{ color: "var(--primary-text)" }} /></div>
                  <span className="db-card-title" style={{ overflow: "visible", whiteSpace: "nowrap" }}>Performance</span>
                </div>
                <div className="db-chart-tabs">
                  {(["7d", "30d", "90d"] as const).map(r => (
                    <button key={r} className={`db-chart-tab ${chartRange === r ? "active" : ""}`} onClick={() => setChartRange(r)}>
                      {r.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
              <div className="db-chart-area">
                <PerformanceChart views={perfViews} clips={perfClips} />
                <div className="db-chart-legend">
                  <span style={{ color: "var(--primary-text)" }}>● Views</span>
                  <span style={{ color: "var(--secondary)" }}>‒‒ Clips</span>
                </div>
              </div>
              <div className="db-chart-stats">
                {[
                  { label: "Views",      value: perfViewsTotal > 0 ? fmtNum(perfViewsTotal) : "—",      trend: "—" },
                  { label: "Clips",      value: String(totalClips),                                       trend: "—" },
                  { label: "Watch Time", value: perfWatchTime > 0 ? `${perfWatchTime}h` : "—",            trend: "—" },
                ].map(({ label, value, trend }) => (
                  <div key={label} className="db-chart-stat">
                    <div className="db-chart-stat-label">{label}</div>
                    <div className="db-chart-stat-val">{value}</div>
                    <div className="db-chart-stat-trend">{trend}</div>
                  </div>
                ))}
              </div>
            </Card>

            {/* 10. AI Activity (4×2) */}
            <Card className="db-activity" style={{ animationDelay: "420ms" }}>
              <CardHeader
                icon={<Zap size={13} style={{ color: "var(--warning)" }} />}
                title="AI Activity"
                action={<button className="db-card-link" onClick={() => router.push("/videos")}>All videos <ArrowRight size={11} /></button>}
              />
              <div className="db-activity-list">
                {activityItems.length === 0 ? (
                  <div className="empty-state" style={{ padding: "16px 0" }}>
                    <div className="empty-title" style={{ fontSize: 12 }}>No activity yet</div>
                    <div className="empty-desc" style={{ fontSize: 11 }}>Upload a video to start the pipeline.</div>
                  </div>
                ) : activityItems.map(entry => {
                  const dot = ADOT[entry.type];
                  return (
                    <div key={entry.id} className="db-activity-item">
                      <div className="db-activity-dot" style={{ borderColor: dot.border, background: dot.bg, color: dot.color }}>
                        {entry.type === "success" && <CheckCircle size={10} />}
                        {entry.type === "info"    && <BarChart2    size={10} />}
                        {entry.type !== "success" && entry.type !== "info" && <AlertCircle size={10} />}
                      </div>
                      <div className="db-activity-content">
                        <div className="db-activity-title">{entry.title}</div>
                        <div className="db-activity-time">{entry.time} · {entry.source}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* 11. Pipeline Status (4×2) */}
            <Card className="db-pipeline" style={{ animationDelay: "460ms" }}>
              <CardHeader
                icon={<PlayCircle size={13} style={{ color: pipelineActive ? "#4d9fff" : "var(--text-3)" }} />}
                title="Pipeline Status"
                badge={
                  pipelineActive ? (
                    <span className="db-live-badge"><span className="db-live-dot" />Active</span>
                  ) : (
                    <span className="db-idle-badge">Idle</span>
                  )
                }
              />
              <div className="db-pipeline-stages">
                {PIPELINE_STAGES.map((stage, i) => {
                  const state = !pipelineActive ? "pending" : activeStageIdx > i ? "done" : activeStageIdx === i ? "active" : "pending";
                  return (
                    <div key={stage.key} className={`db-stage ${state}`}>
                      {i < PIPELINE_STAGES.length - 1 && <div className={`db-stage-line ${state === "done" ? "done" : ""}`} />}
                      <div className="db-stage-circle">{state === "done" ? "✓" : state === "active" ? "◉" : i + 1}</div>
                      <div className="db-stage-label">{stage.label}</div>
                    </div>
                  );
                })}
              </div>
              <div className="db-pipeline-bar-bg">
                <div
                  className={`db-pipeline-bar-fill${pipelineActive ? " active" : ""}`}
                  style={{ width: `${pipelineProgress}%` }}
                />
              </div>
              <div className="db-pipeline-summary">
                <span className="db-pipeline-summary-text">
                  {pipelineActive
                    ? (() => {
                        const stageLabel = PIPELINE_STAGES[activeStageIdx >= 0 ? activeStageIdx : 0]?.label ?? "Processing";
                        const dlPct = pipelineStatus?.download_progress;
                        const doing = pipelineStatus?.current_stage
                          ? (CHECKPOINT_DOING[pipelineStatus.current_stage] ?? stageLabel)
                          : stageLabel;
                        // For sub-stage progress (downloading/transcribing) show the raw stage %
                        // so it matches what AI Activity shows. Bar still shows overall pipeline %.
                        const isSubStage = pipelineStatus?.current_stage === "downloading" || pipelineStatus?.current_stage === "transcribing";
                        const suffix = (isSubStage && dlPct)
                          ? ` · ${dlPct}%`
                          : ` · ${pipelineProgress}%`;
                        return `Stage ${(activeStageIdx + 1) || 1} of ${PIPELINE_STAGES.length} · ${doing}${suffix}`;
                      })()
                    : "No active pipeline"}
                </span>
                {pipelineActive && (
                  <span className="db-pipeline-eta">
                    {pipelineStatus?.eta_seconds
                      ? `ETA: ~${Math.max(1, Math.round(pipelineStatus.eta_seconds / 60))} min`
                      : pipelineStatus?.current_stage === "downloading"
                        ? `Downloading ${pipelineStatus?.download_progress ?? 0}%`
                        : `~${Math.max(1, Math.ceil((100 - pipelineProgress) / 8))} min`}
                  </span>
                )}
              </div>
            </Card>

          </div>
        </div>
      </div>

      {/* Upload Modal */}
      {showUploader && (
        <div
          onClick={() => setShowUploader(false)}
          style={{
            position: "fixed", inset: 0, zIndex: 50,
            display: "flex", alignItems: "center", justifyContent: "center", padding: 20,
            background: "rgba(0,0,0,0.75)", backdropFilter: "blur(8px)",
          }}
        >
          <div onClick={e => e.stopPropagation()} style={{ width: "100%", maxWidth: 520 }}>
            <VideoUploader onSuccess={() => setShowUploader(false)} />
          </div>
        </div>
      )}
    </>
  );
}
