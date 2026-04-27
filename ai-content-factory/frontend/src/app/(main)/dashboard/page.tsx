"use client";
import { useRouter } from "next/navigation";
import Image from "next/image";
import {
  Video, Scissors, Eye, CheckCircle,
  Upload, ArrowRight, Zap, Play, Flame,
  ChevronRight, TrendingUp,
  Youtube,
} from "lucide-react";
import { Header } from "@/components/layout/Header";
import { useVideos, useVideoStatus, useYoutubeStats, useClipStats } from "@/lib/queries";
import { formatRelativeTime } from "@/lib/utils";
import { useState, useEffect, useRef } from "react";
import { VideoUploader } from "@/components/video/VideoUploader";

/* ─── Animated Counter ──────────────────────────────────── */
function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);
  const displayRef = useRef(0);
  const raf = useRef<number | null>(null);
  useEffect(() => {
    const start = displayRef.current;
    const end = value;
    if (start === end) return;
    const t0 = performance.now();
    const step = (now: number) => {
      const p = Math.min((now - t0) / 650, 1);
      const e = 1 - Math.pow(1 - p, 3);
      const current = Math.round(start + (end - start) * e);
      displayRef.current = current;
      setDisplay(current);
      if (p < 1) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); };
  }, [value]);
  return <>{display}</>;
}

/* ─── Skeleton Stat Card ────────────────────────────────── */
function SkeletonStatCard() {
  return (
    <div className="stat-card">
      <div className="skeleton" style={{ width: 34, height: 34, borderRadius: 6, marginBottom: 16 }} />
      <div className="skeleton" style={{ width: 80, height: 34, borderRadius: 6, marginBottom: 8 }} />
      <div className="skeleton" style={{ width: 100, height: 12, borderRadius: 4 }} />
    </div>
  );
}

/* ─── Stat Card ─────────────────────────────────────────── */
type StatColor = "primary" | "secondary" | "warning" | "danger";
const STAT_CFG: Record<StatColor, { glow: string; iconBg: string; iconColor: string }> = {
  primary:   { glow: "var(--primary)",   iconBg: "var(--primary-dim)",   iconColor: "var(--primary-text)" },
  secondary: { glow: "var(--secondary)", iconBg: "var(--secondary-dim)", iconColor: "var(--secondary)" },
  warning:   { glow: "var(--warning)",   iconBg: "var(--warning-dim)",   iconColor: "var(--warning)" },
  danger:    { glow: "var(--danger)",    iconBg: "var(--danger-dim)",    iconColor: "var(--danger)" },
};

function StatCard({
  label, value, icon: Icon, color = "primary", delay = 0,
}: {
  label: string; value: number; icon: React.ElementType; color?: StatColor; delay?: number;
}) {
  const c = STAT_CFG[color];
  return (
    <div className="stat-card" style={{ animationDelay: `${delay}ms` }}>
      <div className="stat-card-glow" style={{ background: c.glow }} />
      <div className="stat-icon" style={{ background: c.iconBg }}>
        <Icon size={15} color={c.iconColor} />
      </div>
      <div className={`stat-number c-${color}`}>
        <AnimatedNumber value={value} />
      </div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

/* ─── Pipeline Stage Track ──────────────────────────────── */
const STAGES = [
  { key: "input_validated", short: "Validate" },
  { key: "transcript_done", short: "Transcribe" },
  { key: "ai_done",         short: "AI Score" },
  { key: "qc_done",         short: "QC" },
  { key: "clips_done",      short: "Cut" },
  { key: "review_ready",    short: "Ready" },
];

function PipelineTrack({ videoId, title }: { videoId: string; title?: string }) {
  const { data: status } = useVideoStatus(videoId);
  if (!status) return null;
  const curr = STAGES.findIndex(s => s.key === status.current_stage);

  return (
    <div className="pipeline-track anim-4">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{
            width: 7, height: 7, borderRadius: "50%",
            background: "var(--primary)", boxShadow: "0 0 8px var(--primary)",
            animation: "pulseGlow 2s infinite",
          }} />
          <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text-1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 180 }}>
            {title ?? "Processing…"}
          </span>
        </div>
        <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--primary-text)", fontWeight: 600 }}>
          {status.progress_percent}%
        </span>
      </div>

      {/* Stage dots */}
      <div style={{ display: "flex", alignItems: "center" }}>
        {STAGES.map((stage, i) => {
          const done   = curr > i;
          const active = curr === i;
          return (
            <div key={stage.key} style={{ display: "flex", alignItems: "center", flex: 1 }}>
              <div style={{ flex: "0 0 auto", display: "flex", flexDirection: "column", alignItems: i === 0 ? "flex-start" : i === STAGES.length - 1 ? "flex-end" : "center", width: "100%" }}>
                <div style={{
                  width: 22, height: 22, borderRadius: "50%",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 10, fontWeight: 600, fontFamily: "var(--font-mono)",
                  background: done ? "var(--secondary-dim)" : active ? "var(--primary-dim)" : "rgba(255,255,255,0.04)",
                  border: `1px solid ${done ? "rgba(0,212,170,0.4)" : active ? "var(--primary)" : "rgba(255,255,255,0.08)"}`,
                  color: done ? "var(--secondary)" : active ? "var(--primary-text)" : "var(--text-4)",
                  boxShadow: active ? "0 0 10px var(--primary-glow)" : "none",
                  transform: active ? "scale(1.15)" : "scale(1)",
                  transition: "all 500ms ease",
                }}>
                  {done ? "✓" : i + 1}
                </div>
                <span style={{
                  marginTop: 4, fontSize: 9, fontFamily: "var(--font-mono)", letterSpacing: "0.03em",
                  color: done ? "var(--secondary)" : active ? "var(--primary-text)" : "var(--text-4)",
                  whiteSpace: "nowrap",
                }}>
                  {stage.short}
                </span>
              </div>
              {i < STAGES.length - 1 && (
                <div style={{
                  height: 1, flex: 1, margin: "0 3px 14px",
                  background: done
                    ? "linear-gradient(90deg, rgba(0,212,170,0.5), rgba(0,212,170,0.2))"
                    : active
                    ? "linear-gradient(90deg, var(--primary), rgba(124,111,255,0.15))"
                    : "rgba(255,255,255,0.06)",
                  transition: "all 500ms ease",
                }} />
              )}
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div className="pipeline-bar-bg">
        <div className="pipeline-bar-fill" style={{ width: `${status.progress_percent}%` }} />
      </div>
    </div>
  );
}

/* ─── Video Row ─────────────────────────────────────────── */
const STATUS_MAP: Record<string, { dot: string; label: string; bg: string }> = {
  processing: { dot: "var(--primary)",   label: "Processing", bg: "var(--primary-dim)" },
  review:     { dot: "var(--warning)",   label: "Review",     bg: "var(--warning-dim)" },
  done:       { dot: "var(--secondary)", label: "Done",       bg: "var(--secondary-dim)" },
  error:      { dot: "var(--danger)",    label: "Error",      bg: "var(--danger-dim)" },
  queued:     { dot: "var(--text-3)",    label: "Queued",     bg: "rgba(255,255,255,0.04)" },
};

function VideoRow({ video, onClick }: { video: { id: string; title?: string; status: string; clips_count: number; created_at: string }; onClick: () => void }) {
  const s = STATUS_MAP[video.status] ?? STATUS_MAP.queued;
  return (
    <div className="video-row" onClick={onClick}>
      <div className="video-thumb">
        <Play size={12} color="var(--text-4)" />
      </div>
      <div className="video-info">
        <div className="video-title">{video.title ?? "Untitled Video"}</div>
        <div className="video-meta">
          {formatRelativeTime(video.created_at)}
          {video.clips_count > 0 && (
            <> &middot; <span style={{ color: "var(--secondary)" }}>{video.clips_count} clips</span></>
          )}
        </div>
      </div>
      <div className="status-pill" style={{ background: s.bg }}>
        <div className="status-dot" style={{ background: s.dot }} />
        <span style={{ color: s.dot }}>{s.label}</span>
      </div>
      <ChevronRight size={13} color="var(--text-4)" style={{ flexShrink: 0 }} className="row-chevron" />
    </div>
  );
}

/* ─── Dashboard Page ────────────────────────────────────── */
export default function DashboardPage() {
  const router = useRouter();
  const [showUploader, setShowUploader] = useState(false);
  const { data: allVideos = [], isLoading } = useVideos();
  const { data: processingVideos = [] } = useVideos({ status: "processing" });
  const { data: reviewVideos = [] } = useVideos({ status: "review" });
  const { data: ytData } = useYoutubeStats();
  const { data: clipStats } = useClipStats();

  const totalClips    = clipStats?.total     ?? 0;
  const pendingReview = clipStats?.pending   ?? 0;
  const publishedClips = clipStats?.published ?? 0;

  const [greeting, setGreeting] = useState<string>("");
  useEffect(() => {
    const h = new Date().getHours();
    setGreeting(h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening");
  }, []);

  return (
    <>
      <Header
        breadcrumb={[{ label: "Dashboard" }]}
        actions={
          <button className="btn-primary" onClick={() => setShowUploader(true)}>
            <Upload size={13} />
            Upload Video
          </button>
        }
      />

      <div className="page-scroll">
        <div className="page-body">

          {/* Page heading */}
          <div className="page-heading anim-0">
            <div className="page-heading-eyebrow">{greeting}</div>
            <h1 className="page-heading-title">
              Content Pipeline{" "}
              <span className="gradient">Overview</span>
            </h1>
          </div>

          {/* YouTube Channel Widget — shows when connected */}
          {ytData?.connected && ytData.accounts.length > 0 && (
            <div
              className="anim-1"
              style={{ display: "flex", flexWrap: "wrap", gap: 10 }}
            >
              {ytData.accounts.map((acc) => (
                <div key={acc.channel_id} className="yt-widget">
                  <div className="yt-widget-avatar">
                    {acc.thumbnail_url
                      ? <Image src={acc.thumbnail_url} alt={acc.channel_name ?? ""} width={38} height={38} style={{ borderRadius: "50%", objectFit: "cover" }} />
                      : <Youtube size={16} color="var(--danger)" />}
                  </div>
                  <div className="yt-widget-info">
                    <div className="yt-widget-name">{acc.channel_name ?? acc.channel_id}</div>
                    {acc.subscriber_count !== undefined && (
                      <div className="yt-widget-subs">
                        {acc.subscriber_count >= 1_000_000
                          ? `${(acc.subscriber_count / 1_000_000).toFixed(1)}M subs`
                          : acc.subscriber_count >= 1_000
                          ? `${(acc.subscriber_count / 1_000).toFixed(1)}K subs`
                          : `${acc.subscriber_count} subs`}
                      </div>
                    )}
                  </div>
                  <div className="yt-widget-badge">
                    <Youtube size={10} />
                    YouTube
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Stats row */}
          <div className="stats-row">
            {isLoading ? (
              <><SkeletonStatCard /><SkeletonStatCard /><SkeletonStatCard /><SkeletonStatCard /></>
            ) : (
              <>
                <div className="anim-0"><StatCard label="Total Videos"    value={allVideos.length}  icon={Video}       color="primary"   /></div>
                <div className="anim-1"><StatCard label="Clips Generated" value={totalClips}        icon={Scissors}    color="secondary" /></div>
                <div className="anim-2"><StatCard label="Pending Review"  value={pendingReview}     icon={Eye}         color="warning"   /></div>
                <div className="anim-3"><StatCard label="Published"       value={publishedClips}    icon={CheckCircle} color="danger"    /></div>
              </>
            )}
          </div>

          {/* Active Pipeline */}
          {processingVideos.length > 0 && (
            <div className="panel anim-4">
              <div className="panel-hd">
                <div className="panel-hd-left">
                  <div className="panel-icon" style={{ background: "var(--primary-dim)" }}>
                    <Zap size={13} color="var(--primary-text)" />
                  </div>
                  <span className="panel-title">Active Pipeline</span>
                  <span className="panel-badge">{processingVideos.length} job{processingVideos.length !== 1 && "s"}</span>
                </div>
                <div style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--primary)", boxShadow: "0 0 8px var(--primary)", animation: "pulseGlow 2s infinite" }} />
              </div>
              <div style={{ padding: "14px" }}>
                <div className="pipeline-grid">
                  {processingVideos.map(v => (
                    <PipelineTrack key={v.id} videoId={v.id} title={v.title ?? undefined} />
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Main 2-col grid */}
          <div className="two-col-grid">

            {/* Recent Videos */}
            <div className="panel anim-4">
              <div className="panel-hd">
                <div className="panel-hd-left">
                  <div className="panel-icon" style={{ background: "rgba(255,255,255,0.04)" }}>
                    <Video size={12} color="var(--text-3)" />
                  </div>
                  <span className="panel-title">Recent Videos</span>
                  {!isLoading && (
                    <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-3)" }}>
                      {allVideos.length} total
                    </span>
                  )}
                </div>
                <button className="btn-link" onClick={() => router.push("/videos")}>
                  All videos <ArrowRight size={11} />
                </button>
              </div>

              <div style={{ padding: "6px 0" }}>
                {isLoading ? (
                  <div style={{ padding: "8px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
                    {[...Array(5)].map((_, i) => (
                      <div key={i} style={{ display: "flex", gap: 12, alignItems: "center" }}>
                        <div className="skeleton" style={{ width: 52, height: 33, borderRadius: 6, flexShrink: 0 }} />
                        <div style={{ flex: 1 }}>
                          <div className="skeleton" style={{ height: 13, width: "65%", borderRadius: 4, marginBottom: 6 }} />
                          <div className="skeleton" style={{ height: 11, width: "35%", borderRadius: 4 }} />
                        </div>
                        <div className="skeleton" style={{ height: 22, width: 70, borderRadius: 20 }} />
                      </div>
                    ))}
                  </div>
                ) : allVideos.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-icon">
                      <Upload size={20} color="var(--primary-text)" />
                    </div>
                    <div className="empty-title">No videos yet</div>
                    <div className="empty-desc">Upload your first long-form video to start the AI pipeline.</div>
                    <button className="btn-primary" onClick={() => setShowUploader(true)}>
                      <Upload size={13} /> Upload Video
                    </button>
                  </div>
                ) : (
                  allVideos.slice(0, 8).map(v => (
                    <VideoRow
                      key={v.id}
                      video={v}
                      onClick={() => router.push(`/videos/${v.id}`)}
                    />
                  ))
                )}
              </div>
            </div>

            {/* Review Queue */}
            <div className="panel anim-5">
              <div className="panel-hd">
                <div className="panel-hd-left">
                  <div className="panel-icon" style={{ background: "var(--warning-dim)" }}>
                    <Flame size={13} color="var(--warning)" />
                  </div>
                  <span className="panel-title">Review Queue</span>
                  {reviewVideos.length > 0 && (
                    <span className="panel-badge" style={{ background: "var(--warning-dim)", color: "var(--warning)", borderColor: "rgba(245,158,11,0.25)" }}>
                      {reviewVideos.length}
                    </span>
                  )}
                </div>
                {reviewVideos.length > 0 && (
                  <button className="btn-link" onClick={() => router.push("/review")}>
                    Review all <ArrowRight size={11} />
                  </button>
                )}
              </div>

              {reviewVideos.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon" style={{ background: "var(--warning-dim)", borderColor: "rgba(245,158,11,0.2)" }}>
                    <TrendingUp size={18} color="var(--warning)" />
                  </div>
                  <div className="empty-title">Queue is clear</div>
                  <div className="empty-desc">Clips will appear here once AI processing completes.</div>
                </div>
              ) : (
                <div style={{ padding: "8px 0" }}>
                  {reviewVideos.slice(0, 6).map((v, i) => (
                    <div
                      key={v.id}
                      className="review-item"
                      onClick={() => router.push(`/videos/${v.id}`)}
                    >
                      <div className="review-num">{i + 1}</div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="review-title">{v.title ?? "Untitled"}</div>
                        <div className="review-meta">{v.clips_count} clip{v.clips_count !== 1 && "s"} ready</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

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
