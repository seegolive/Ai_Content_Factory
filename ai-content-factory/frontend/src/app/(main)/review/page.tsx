"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle, XCircle, Play, Pause, TrendingUp, AlertTriangle,
  Edit2, Check, ChevronDown, Filter, Clock, Hash,
  SkipForward, SkipBack, Upload,
} from "lucide-react";
import { Header } from "@/components/layout/Header";
import { useVideos, useClips, useReviewClip, useUpdateClip } from "@/lib/queries";
import { useUIStore } from "@/stores/uiStore";
import { clipsApi } from "@/lib/api";
import { formatDuration } from "@/lib/utils";
import { toast } from "sonner";
import type { Clip, MomentType } from "@/types";
import { BulkActions } from "@/components/clips/BulkActions";

// ── Helpers ─────────────────────────────────────────────────────────────────
function fmtTime(s: number): string {
  if (!s || isNaN(s)) return "0:00";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

// ── Duration rules (mirrors backend MOMENT_DURATION_RULES) ──────────────────
const DURATION_RULES: Record<MomentType | "default", { min: number; idealMin: number; idealMax: number; max: number }> = {
  clutch:      { min: 45, idealMin: 55, idealMax: 75,  max: 90  },
  funny:       { min: 20, idealMin: 25, idealMax: 45,  max: 60  },
  achievement: { min: 60, idealMin: 70, idealMax: 90,  max: 120 },
  rage:        { min: 30, idealMin: 40, idealMax: 60,  max: 75  },
  epic:        { min: 45, idealMin: 60, idealMax: 90,  max: 100 },
  fail:        { min: 20, idealMin: 30, idealMax: 50,  max: 60  },
  tutorial:    { min: 45, idealMin: 60, idealMax: 90,  max: 120 },
  default:     { min: 30, idealMin: 45, idealMax: 75,  max: 90  },
};

function getDurationStatus(
  duration: number,
  momentType?: MomentType
): "ideal" | "short" | "long" | "over" {
  const rule = (momentType ? DURATION_RULES[momentType] : null) ?? DURATION_RULES.default;
  if (duration < rule.min) return "over"; // under min — error
  if (duration > rule.max) return "over";
  if (duration < rule.idealMin || duration > rule.idealMax) return "short";
  return "ideal";
}

// ── Moment config ────────────────────────────────────────────────────────────
const MOMENT_CFG: Record<MomentType, { emoji: string; label: string; color: string }> = {
  clutch:      { emoji: "🎯", label: "Clutch",      color: "#6C63FF" },
  funny:       { emoji: "😂", label: "Funny",       color: "#00D4AA" },
  achievement: { emoji: "🏆", label: "Achievement", color: "#F59E0B" },
  rage:        { emoji: "😤", label: "Rage",        color: "#EF4444" },
  epic:        { emoji: "⚡", label: "Epic",        color: "#8B5CF6" },
  fail:        { emoji: "💀", label: "Fail",        color: "#6B7280" },
  tutorial:    { emoji: "📖", label: "Tutorial",    color: "#3B82F6" },
};

type SortKey = "viral_score" | "duration" | "moment_type";
type FilterType = MomentType | "all";
type FormatMode = "16:9" | "9:16" | "1:1";

function viralColor(score: number) {
  if (score >= 75) return "var(--secondary)";
  if (score >= 50) return "var(--warning)";
  return "var(--danger)";
}

// ── DurationBadge ─────────────────────────────────────────────────────────────
function DurationBadge({ duration, momentType }: { duration: number; momentType?: MomentType }) {
  const status = getDurationStatus(duration, momentType);
  const rule = (momentType ? DURATION_RULES[momentType] : null) ?? DURATION_RULES.default;
  const label = `${Math.round(duration)}s`;
  const colors: Record<typeof status, { bg: string; border: string; text: string }> = {
    ideal: { bg: "rgba(0,212,170,0.10)", border: "rgba(0,212,170,0.35)", text: "#00D4AA" },
    short: { bg: "rgba(245,158,11,0.10)", border: "rgba(245,158,11,0.35)", text: "#F59E0B" },
    long:  { bg: "rgba(245,158,11,0.10)", border: "rgba(245,158,11,0.35)", text: "#F59E0B" },
    over:  { bg: "rgba(239,68,68,0.10)",  border: "rgba(239,68,68,0.35)",  text: "#EF4444" },
  };
  const c = colors[status];
  return (
    <span
      title={`Ideal: ${rule.idealMin}–${rule.idealMax}s`}
      style={{
        display: "inline-flex", alignItems: "center", gap: 4,
        fontSize: 10, fontWeight: 700, fontFamily: "var(--font-mono)",
        padding: "2px 7px", borderRadius: 99,
        background: c.bg, border: `1px solid ${c.border}`, color: c.text,
      }}
    >
      <Clock size={9} />
      {label}
    </span>
  );
}

// ── MomentBadge ──────────────────────────────────────────────────────────────
function MomentBadge({ type, small }: { type?: string; small?: boolean }) {
  const cfg = type ? MOMENT_CFG[type as MomentType] : null;
  if (!cfg) return null;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 3,
      fontSize: small ? 10 : 11, fontWeight: 600,
      padding: small ? "1px 6px" : "2px 8px",
      borderRadius: 99,
      background: cfg.color + "18",
      border: `1px solid ${cfg.color}40`,
      color: cfg.color,
      whiteSpace: "nowrap",
    }}>
      {cfg.emoji} {cfg.label}
    </span>
  );
}

// ── Empty / All-reviewed states ───────────────────────────────────────────────
function EmptyState() {
  return (
    <div className="page-scroll">
      <div className="page-body">
        <div className="empty-state" style={{ paddingTop: 80 }}>
          <div className="empty-icon" style={{ background: "var(--secondary-dim)", borderColor: "rgba(0,212,170,0.2)" }}>
            <CheckCircle size={22} color="var(--secondary)" />
          </div>
          <div className="empty-title">Review queue is empty</div>
          <div className="empty-desc">
            All clips have been reviewed. New clips will appear here after AI processing.
          </div>
        </div>
      </div>
    </div>
  );
}

function AllReviewedBanner({ total }: { total: number }) {
  return (
    <div style={{
      flex: 1, display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: 16,
      padding: 40, textAlign: "center",
    }}>
      <div style={{
        width: 64, height: 64, borderRadius: "50%",
        background: "rgba(0,212,170,0.12)", border: "1px solid rgba(0,212,170,0.25)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <CheckCircle size={28} color="var(--secondary)" />
      </div>
      <div>
        <div style={{ fontSize: 18, fontWeight: 700, color: "var(--text-1)", marginBottom: 6 }}>
          All {total} clips reviewed
        </div>
        <div style={{ fontSize: 13, color: "var(--text-3)", maxWidth: 320 }}>
          Change the filter above to review more, or wait for new clips from the pipeline.
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ReviewPage() {
  const router = useRouter();
  const { selectedClips, toggleClipSelection, clearSelection, reviewActiveClipId, setReviewActiveClip } = useUIStore();

  const { data: reviewVideos = [] } = useVideos({ status: "review" });
  const [selectedVideoId, setSelectedVideoId] = useState<string>("");

  useEffect(() => {
    if (reviewVideos.length > 0 && !reviewVideos.find((v) => v.id === selectedVideoId)) {
      setSelectedVideoId(reviewVideos[0].id);
    }
  }, [reviewVideos, selectedVideoId]);

  const { data: clips = [] } = useClips(selectedVideoId);
  const pendingClips = clips.filter((c) => c.review_status === "pending");
  const approvedClips = clips.filter((c) => c.review_status === "approved");

  // Queue mode toggle
  const [queueMode, setQueueMode] = useState<"pending" | "approved">("pending");
  const activeList = queueMode === "approved" ? approvedClips : pendingClips;

  // Sort & filter state
  const [sortKey, setSortKey] = useState<SortKey>("viral_score");
  const [filterType, setFilterType] = useState<FilterType>("all");
  const [formatMode, setFormatMode] = useState<FormatMode>("16:9");
  const [showSortMenu, setShowSortMenu] = useState(false);

  const sortedFilteredClips = [...activeList]
    .filter((c) => filterType === "all" || c.moment_type === filterType)
    .sort((a, b) => {
      if (sortKey === "viral_score") return (b.viral_score ?? 0) - (a.viral_score ?? 0);
      if (sortKey === "duration") return (b.duration ?? 0) - (a.duration ?? 0);
      if (sortKey === "moment_type") return (a.moment_type ?? "").localeCompare(b.moment_type ?? "");
      return 0;
    });

  const activeClip = sortedFilteredClips.find((c) => c.id === reviewActiveClipId) ?? sortedFilteredClips[0];

  const { mutateAsync: reviewClip } = useReviewClip();
  const { mutateAsync: updateClip } = useUpdateClip();

  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [videoDuration, setVideoDuration] = useState(0);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const sortMenuRef = useRef<HTMLDivElement>(null);
  const [streamToken, setStreamToken] = useState<string | null>(null);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);

  // Fetch stream token whenever clip changes
  useEffect(() => {
    if (!activeClip?.id) { setStreamToken(null); setStreamUrl(null); return; }
    let cancelled = false;
    setCurrentTime(0); setVideoDuration(0); setIsPlaying(false);
    clipsApi.getStreamToken(activeClip.id)
      .then((res) => { if (!cancelled) setStreamToken(res.data.token); })
      .catch(() => { if (!cancelled) { setStreamToken(null); setStreamUrl(null); } });
    return () => { cancelled = true; };
  }, [activeClip?.id]);

  // Rebuild stream URL whenever token or format changes
  useEffect(() => {
    if (!activeClip?.id || !streamToken) { setStreamUrl(null); return; }
    const fmt = formatMode === "9:16" ? "vertical" : undefined;
    setStreamUrl(clipsApi.streamUrl(activeClip.id, streamToken, fmt));
    setCurrentTime(0); setVideoDuration(0); setIsPlaying(false);
  }, [activeClip?.id, streamToken, formatMode]);

  useEffect(() => {
    if (!reviewActiveClipId && sortedFilteredClips.length > 0) {
      setReviewActiveClip(sortedFilteredClips[0].id);
    }
  }, [reviewActiveClipId, sortedFilteredClips, setReviewActiveClip]);

  // Reset title-edit state when active clip changes
  useEffect(() => {
    setEditingTitle(false);
  }, [activeClip?.id]);

  // Close sort dropdown on outside click
  useEffect(() => {
    if (!showSortMenu) return;
    const handler = (e: MouseEvent) => {
      if (sortMenuRef.current && !sortMenuRef.current.contains(e.target as Node)) {
        setShowSortMenu(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showSortMenu]);

  const togglePlay = useCallback(() => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) { videoRef.current.play(); setIsPlaying(true); }
    else { videoRef.current.pause(); setIsPlaying(false); }
  }, []);

  const handleReview = useCallback(async (action: "approve" | "reject") => {
    if (!activeClip || reviewing) return;
    setReviewing(true);
    try {
      await reviewClip({ clipId: activeClip.id, action });
      toast.success(action === "approve" ? "✓ Approved" : "✗ Rejected");
      const idx = sortedFilteredClips.findIndex((c) => c.id === activeClip.id);
      if (idx < sortedFilteredClips.length - 1) setReviewActiveClip(sortedFilteredClips[idx + 1].id);
    } catch { toast.error("Action failed"); }
    finally { setReviewing(false); }
  }, [activeClip, reviewing, reviewClip, sortedFilteredClips, setReviewActiveClip]);

  const handleApproveAndPublish = useCallback(async () => {
    if (!activeClip || reviewing) return;
    setReviewing(true);
    try {
      await reviewClip({ clipId: activeClip.id, action: "approve" });
      router.push(`/publish/${activeClip.id}`);
    } catch { toast.error("Approve failed"); setReviewing(false); }
  }, [activeClip, reviewing, reviewClip, router]);

  const handlePublishApproved = useCallback(() => {
    if (!activeClip) return;
    router.push(`/publish/${activeClip.id}`);
  }, [activeClip, router]);

  const handleSaveTitle = async () => {
    if (!activeClip || !titleDraft.trim()) return;
    await updateClip({ clipId: activeClip.id, data: { title: titleDraft } });
    setEditingTitle(false);
    toast.success("Title saved");
  };

  const handleSeek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!videoRef.current || !videoDuration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const t = ratio * videoDuration;
    videoRef.current.currentTime = t;
    setCurrentTime(t);
  }, [videoDuration]);

  const skip = useCallback((sec: number) => {
    if (!videoRef.current) return;
    const next = Math.max(0, Math.min(videoRef.current.duration || 0, videoRef.current.currentTime + sec));
    videoRef.current.currentTime = next;
    setCurrentTime(next);
  }, []);

  const navigateTo = useCallback((dir: "prev" | "next") => {
    if (!activeClip) return;
    const idx = sortedFilteredClips.findIndex((c) => c.id === activeClip.id);
    if (dir === "next" && idx < sortedFilteredClips.length - 1) setReviewActiveClip(sortedFilteredClips[idx + 1].id);
    if (dir === "prev" && idx > 0) setReviewActiveClip(sortedFilteredClips[idx - 1].id);
  }, [activeClip, sortedFilteredClips, setReviewActiveClip]);

  const handleKeyDownRef = useRef<(e: KeyboardEvent) => void>(() => {});
  handleKeyDownRef.current = (e: KeyboardEvent) => {
    const target = e.target as HTMLElement;
    if (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
    if (!activeClip || editingTitle) return;
    switch (e.key.toLowerCase()) {
      case "a": e.preventDefault(); handleReview("approve"); break;
      case "r": e.preventDefault(); handleReview("reject"); break;
      case "p": e.preventDefault();
        if (queueMode === "approved") handlePublishApproved();
        else handleApproveAndPublish();
        break;
      case "j": case "arrowdown": e.preventDefault(); navigateTo("next"); break;
      case "k": case "arrowup": e.preventDefault(); navigateTo("prev"); break;
      case " ": e.preventDefault(); togglePlay(); break;
      case "b": e.preventDefault(); toggleClipSelection(activeClip.id); break;
    }
  };

  useEffect(() => {
    const handler = (e: KeyboardEvent) => handleKeyDownRef.current(e);
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Unique moment types for filter pills
  const presentTypes = Array.from(new Set(activeList.map((c) => c.moment_type).filter(Boolean))) as MomentType[];

  const SORT_LABELS: Record<SortKey, string> = {
    viral_score: "Viral Score",
    duration: "Duration",
    moment_type: "Type",
  };

  // Score pill class helper
  function scorePillClass(score: number) {
    if (score >= 75) return "";
    if (score >= 50) return " mid";
    return " low";
  }

  if (pendingClips.length === 0 && approvedClips.length === 0) return <EmptyState />;

  return (
    <>
      <Header breadcrumb={[{ label: "Review Queue" }]} />

      <div className="review-shell">

        {/* ── COL 1: Clip list ──────────────────────────────────────────── */}
        <div className="review-list">

          {/* List header */}
          <div className="review-list-hd">
            {/* Pending / Approved tabs */}
            <div className="rq-mode-tabs">
              <button
                className={`rq-mode-tab${queueMode === "pending" ? " active" : ""}`}
                onClick={() => { setQueueMode("pending"); setFilterType("all"); }}
              >
                Pending
                {pendingClips.length > 0 && (
                  <span className="rq-mode-count">{pendingClips.length}</span>
                )}
              </button>
              <button
                className={`rq-mode-tab${queueMode === "approved" ? " active approved" : ""}`}
                onClick={() => { setQueueMode("approved"); setFilterType("all"); }}
              >
                Approved
                {approvedClips.length > 0 && (
                  <span className={`rq-mode-count${queueMode === "approved" ? " approved" : ""}`}>{approvedClips.length}</span>
                )}
              </button>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {selectedClips.length > 0 && (
                <button className="btn-link" onClick={clearSelection} style={{ fontSize: 11 }}>
                  Clear ({selectedClips.length})
                </button>
              )}
              {/* Sort dropdown */}
              <div ref={sortMenuRef} style={{ position: "relative" }}>
                <button
                  onClick={() => setShowSortMenu((v) => !v)}
                  style={{
                    display: "flex", alignItems: "center", gap: 4,
                    fontSize: 10, fontWeight: 600, color: "var(--text-4)",
                    background: "var(--bg-2)", border: "1px solid var(--border-1)",
                    borderRadius: 5, padding: "3px 7px", cursor: "pointer",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  <Filter size={9} />
                  {SORT_LABELS[sortKey]}
                  <ChevronDown size={9} />
                </button>
                {showSortMenu && (
                  <div
                    style={{
                      position: "absolute", right: 0, top: "calc(100% + 4px)",
                      background: "var(--bg-2)", border: "1px solid var(--border-1)",
                      borderRadius: 8, padding: 4, zIndex: 50,
                      boxShadow: "0 8px 32px rgba(0,0,0,0.4)", minWidth: 130,
                    }}
                  >
                    {(["viral_score", "duration", "moment_type"] as SortKey[]).map((key) => (
                      <button
                        key={key}
                        onClick={() => { setSortKey(key); setShowSortMenu(false); }}
                        style={{
                          width: "100%", textAlign: "left",
                          padding: "6px 10px", borderRadius: 5, fontSize: 12,
                          background: sortKey === key ? "var(--primary-dim)" : "transparent",
                          color: sortKey === key ? "var(--primary)" : "var(--text-2)",
                          border: "none", cursor: "pointer",
                        }}
                      >
                        {SORT_LABELS[key]}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Filter chips */}
          <div className="review-filter-row">
            <button
              onClick={() => setFilterType("all")}
              className={`review-filter-chip${filterType === "all" ? " active" : ""}`}
            >All</button>
            {presentTypes.map((t) => {
              const cfg = MOMENT_CFG[t];
              const active = filterType === t;
              return (
                <button
                  key={t}
                  onClick={() => setFilterType(active ? "all" : t)}
                  className={`review-filter-chip fc-${t}${active ? " active" : ""}`}
                  style={{ color: active ? undefined : cfg.color }}
                >
                  {cfg.emoji} {cfg.label}
                </button>
              );
            })}
          </div>

          {/* Video selector (multi-video) */}
          {reviewVideos.length > 1 && (
            <div style={{ padding: "8px 14px", borderBottom: "1px solid var(--border-1)" }}>
              <select
                value={selectedVideoId}
                onChange={(e) => { setSelectedVideoId(e.target.value); clearSelection(); }}
                className="settings-input"
                style={{ fontSize: 11, height: 28, padding: "0 8px", width: "100%" }}
                aria-label="Select video"
              >
                {reviewVideos.map((v) => (
                  <option key={v.id} value={v.id}>{v.title ?? "Untitled"}</option>
                ))}
              </select>
            </div>
          )}

          {/* Clip scroll list */}
          <div className="review-list-scroll">
            {sortedFilteredClips.length === 0 ? (
              <AllReviewedBanner total={pendingClips.length} />
            ) : (
              sortedFilteredClips.map((clip, idx) => {
                const active = clip.id === activeClip?.id;
                const dur = Math.round(clip.duration ?? (clip.end_time - clip.start_time));
                const momentType = clip.moment_type as MomentType | undefined;
                return (
                  <div
                    key={clip.id}
                    onClick={() => setReviewActiveClip(clip.id)}
                    className={`review-clip-item${active ? " active" : ""}`}
                  >
                    {/* Thumbnail */}
                    <div className="review-clip-thumb">
                      <Play size={12} color="var(--text-4)" />
                      <span className="review-clip-duration">{dur}s</span>
                    </div>

                    {/* Info */}
                    <div className="review-clip-info">
                      <div className="review-clip-title">
                        {clip.title ?? `Clip ${idx + 1}`}
                      </div>
                      <div className="review-clip-meta">
                        {clip.viral_score !== undefined && (
                          <span className={`rq-score-pill${scorePillClass(clip.viral_score)}`}>
                            {clip.viral_score}
                          </span>
                        )}
                        {momentType && (
                          <span className={`rq-tag-pill ${momentType}`}>
                            {MOMENT_CFG[momentType].label}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Checkbox */}
                    <div
                      className="rq-checkbox-wrap"
                      style={{ position: "absolute", top: 9, right: 10 }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        checked={selectedClips.includes(clip.id)}
                        onChange={() => toggleClipSelection(clip.id)}
                        style={{ width: 13, height: 13, accentColor: "#00e5a0", cursor: "pointer" }}
                      />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ── COL 2: Video preview ──────────────────────────────────────── */}
        {activeClip ? (
          <div className="review-main">

            {/* Video area */}
            <div
              className="review-video-area"
              onClick={togglePlay}
              style={{ cursor: "pointer" }}
            >
              {/* Format toggle */}
              <div
                onClick={(e) => e.stopPropagation()}
                style={{
                  position: "absolute", top: 12, right: 12, zIndex: 10,
                  display: "flex", gap: 2,
                  background: "rgba(0,0,0,0.6)", backdropFilter: "blur(6px)",
                  borderRadius: 8, padding: 3, border: "1px solid rgba(255,255,255,0.08)",
                }}
              >
                {(["16:9", "9:16", "1:1"] as FormatMode[]).map((fmt) => (
                  <button
                    key={fmt}
                    onClick={() => setFormatMode(fmt)}
                    style={{
                      fontSize: 10, fontWeight: 600, padding: "3px 7px", borderRadius: 5,
                      background: formatMode === fmt ? "var(--primary)" : "transparent",
                      color: formatMode === fmt ? "#fff" : "rgba(255,255,255,0.45)",
                      border: "none", cursor: "pointer",
                    }}
                  >{fmt}</button>
                ))}
              </div>

              {/* Video */}
              <video
                ref={videoRef}
                key={activeClip.id}
                src={streamUrl ?? undefined}
                style={{
                  maxHeight: "100%",
                  maxWidth: "100%",
                  display: "block",
                  aspectRatio: formatMode === "9:16" ? "9/16" : formatMode === "1:1" ? "1/1" : "16/9",
                  objectFit: "contain",
                }}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                onTimeUpdate={() => setCurrentTime(videoRef.current?.currentTime ?? 0)}
                onLoadedMetadata={() => setVideoDuration(videoRef.current?.duration ?? 0)}
                loop
              />

              {/* Nav arrows */}
              <button
                className="review-video-nav prev"
                onClick={(e) => { e.stopPropagation(); navigateTo("prev"); }}
                title="Previous (K/↑)"
              >
                <SkipBack size={14} />
              </button>
              <button
                className="review-video-nav next"
                onClick={(e) => { e.stopPropagation(); navigateTo("next"); }}
                title="Next (J/↓)"
              >
                <SkipForward size={14} />
              </button>

              {/* Play overlay */}
              <div style={{
                position: "absolute", inset: 0,
                display: "flex", alignItems: "center", justifyContent: "center",
                pointerEvents: "none",
                opacity: isPlaying ? 0 : 1,
                transition: "opacity 0.18s",
              }}>
                <div style={{
                  width: 52, height: 52, borderRadius: "50%",
                  background: "rgba(0,229,160,0.18)", border: "1px solid rgba(0,229,160,0.3)",
                  backdropFilter: "blur(4px)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  boxShadow: "0 0 0 0 rgba(0,229,160,0.35)",
                  animation: "rq-pulse-play 2.5s ease-in-out infinite",
                }}>
                  <Play size={20} color="#00e5a0" style={{ marginLeft: 2 }} />
                </div>
              </div>
            </div>

            {/* Media player timeline */}
            <div className="review-timeline">
              {/* Seekbar */}
              <div className="review-timeline-track" onClick={handleSeek}>
                <div className="review-timeline-rail">
                  <div
                    className="review-timeline-fill"
                    style={{ width: videoDuration ? `${(currentTime / videoDuration) * 100}%` : "0%" }}
                  />
                </div>
              </div>
              {/* Controls row */}
              <div className="review-timeline-controls">
                <span className="review-tc-time">{fmtTime(currentTime)}</span>
                <span className="review-tc-sep">/</span>
                <span className="review-tc-time" style={{ color: "var(--text-4)" }}>{fmtTime(videoDuration)}</span>
                <div style={{ flex: 1 }} />
                <button className="review-tc-btn" onClick={() => skip(-10)} title="Back 10s">
                  <SkipBack size={11} />
                </button>
                <button className="review-tc-play" onClick={togglePlay} title="Play / Pause (Space)">
                  {isPlaying
                    ? <Pause size={13} color="#000" />
                    : <Play size={13} color="#000" style={{ marginLeft: 2 }} />}
                </button>
                <button className="review-tc-btn" onClick={() => skip(10)} title="Forward 10s">
                  <SkipForward size={11} />
                </button>
                <div style={{ flex: 1 }} />
                {videoDuration > 0 && (
                  <span className="review-tc-clip-range">
                    {fmtTime(activeClip.start_time)} — {fmtTime(activeClip.end_time)}
                  </span>
                )}
              </div>
            </div>

            {/* Action bar */}
            <div className="review-controls">
              {queueMode === "approved" ? (
                <>
                  <div className="review-controls-buttons">
                    <button
                      onClick={handlePublishApproved}
                      className="review-btn-publish"
                    >
                      <Upload size={13} />
                      Publish Settings
                    </button>
                  </div>
                  <div className="review-controls-shortcuts">
                    <div className="review-shortcut-hint">
                      <div className="review-shortcut-pair"><kbd>P</kbd> publish</div>
                      <div className="review-shortcut-pair"><kbd>Space</kbd> play</div>
                      <div className="review-shortcut-pair"><kbd>J/K</kbd> nav</div>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <div className="review-controls-buttons">
                    <button
                      onClick={handleApproveAndPublish}
                      className="review-btn-approve-publish"
                      disabled={reviewing}
                    >
                      <Upload size={13} />
                      &amp; Publish
                    </button>
                    <button onClick={() => handleReview("approve")} className="review-btn-approve" disabled={reviewing}>
                      <CheckCircle size={13} /> Approve
                    </button>
                    <button onClick={() => handleReview("reject")} className="review-btn-reject" disabled={reviewing}>
                      <XCircle size={13} /> Reject
                    </button>
                  </div>
                  <div className="review-controls-shortcuts">
                    <div className="review-shortcut-hint">
                      <div className="review-shortcut-pair"><kbd>A</kbd> approve</div>
                      <div className="review-shortcut-pair"><kbd>P</kbd> approve+publish</div>
                      <div className="review-shortcut-pair"><kbd>R</kbd> reject</div>
                      <div className="review-shortcut-pair"><kbd>J/K</kbd> nav</div>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        ) : (
          <div className="review-main" style={{ alignItems: "center", justifyContent: "center" }}>
            <span style={{ color: "var(--text-4)", fontSize: 13 }}>Select a clip</span>
          </div>
        )}

        {/* ── COL 3: Detail panel ───────────────────────────────────────── */}
        <div className="review-detail">
          {activeClip ? (
            <>
              <div className="review-detail-scroll">

                {/* Title */}
                <div>
                  <div className="review-detail-title-row">
                    {editingTitle ? (
                      <div style={{ flex: 1, display: "flex", gap: 8 }}>
                        <input
                          autoFocus
                          value={titleDraft}
                          onChange={(e) => setTitleDraft(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleSaveTitle()}
                          className="settings-input"
                          style={{ flex: 1, fontSize: 13 }}
                        />
                        <button className="btn-primary" onClick={handleSaveTitle} style={{ height: 36, padding: "0 12px" }}>
                          <Check size={13} />
                        </button>
                      </div>
                    ) : (
                      <>
                        <div className="review-detail-title">
                          {activeClip.title ?? "Untitled Clip"}
                        </div>
                        <button
                          className="review-edit-btn"
                          onClick={() => { setTitleDraft(activeClip.title ?? ""); setEditingTitle(true); }}
                          title="Edit title"
                        >
                          <Edit2 size={13} />
                        </button>
                      </>
                    )}
                  </div>

                  {/* Meta chips */}
                  <div className="review-meta-row">
                    <span className="review-meta-chip">
                      <Clock size={9} />
                      {formatDuration(activeClip.start_time)} → {formatDuration(activeClip.end_time)}
                    </span>
                    {activeClip.moment_type && (
                      <span className={`rq-tag-pill ${activeClip.moment_type}`} style={{ fontSize: 10, padding: "3px 8px" }}>
                        {MOMENT_CFG[activeClip.moment_type as MomentType]?.emoji}{" "}
                        {MOMENT_CFG[activeClip.moment_type as MomentType]?.label}
                      </span>
                    )}
                  </div>
                </div>

                {/* Viral score gauge */}
                {activeClip.viral_score !== undefined && (
                  <div className="review-score-section">
                    <div className="review-score-hd">
                      <span className="review-score-label">Viral Score</span>
                      <span className="review-score-value">
                        {activeClip.viral_score}<span>/100</span>
                      </span>
                    </div>
                    <div className="review-score-bar">
                      <div
                        className="review-score-bar-fill"
                        style={{ width: `${activeClip.viral_score}%` }}
                      />
                    </div>
                    {/* Duration status below score */}
                    {activeClip.duration !== undefined && (
                      <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 8 }}>
                        <DurationBadge
                          duration={activeClip.duration}
                          momentType={activeClip.moment_type as MomentType}
                        />
                        <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--text-4)" }}>
                          {Math.round(activeClip.duration)}s
                        </span>
                      </div>
                    )}
                  </div>
                )}

                {/* Hook */}
                {activeClip.hook_text && (
                  <div className="review-detail-card">
                    <div className="review-detail-card-hd">
                      <span className="review-detail-card-title">
                        <TrendingUp size={10} />
                        Hook
                      </span>
                    </div>
                    <div className="review-detail-card-body">
                      <blockquote className="review-hook-quote">
                        &ldquo;{activeClip.hook_text}&rdquo;
                      </blockquote>
                    </div>
                  </div>
                )}

                {/* QC Issues */}
                {activeClip.qc_issues.length > 0 && (
                  <div className="review-detail-card">
                    <div className="review-detail-card-hd">
                      <span className="review-detail-card-title" style={{ color: "#ffb347" }}>
                        <AlertTriangle size={10} />
                        QC Issues
                      </span>
                      <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: "#ffb347" }}>
                        {activeClip.qc_issues.length} found
                      </span>
                    </div>
                    <div className="review-detail-card-body">
                      <div className="review-qc-list">
                        {activeClip.qc_issues.map((issue, i) => {
                          const dotClass = issue.severity === "error" ? "err" : issue.severity === "warning" ? "warn" : "info";
                          return (
                            <div key={i} className="review-qc-item">
                              <div className={`review-qc-dot ${dotClass}`} />
                              <span>{issue.description}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}

                {/* Hashtags */}
                {activeClip.hashtags.length > 0 && (
                  <div className="review-detail-card">
                    <div className="review-detail-card-hd">
                      <span className="review-detail-card-title">
                        <Hash size={10} />
                        Hashtags
                      </span>
                      <span style={{ fontSize: 9, fontFamily: "var(--font-mono)", color: "var(--text-4)" }}>
                        {activeClip.hashtags.length} tags
                      </span>
                    </div>
                    <div className="review-detail-card-body">
                      <div className="review-hashtags">
                        {activeClip.hashtags.map((tag) => (
                          <span key={tag} className="review-hashtag">#{tag}</span>
                        ))}
                      </div>
                    </div>
                    {activeClip.ai_provider_used && (
                      <div className="review-generated-by">
                        Generated by
                        <span className="review-ai-badge">{activeClip.ai_provider_used}</span>
                      </div>
                    )}
                    <div style={{ paddingBottom: 6 }} />
                  </div>
                )}

              </div>

              {/* Detail footer */}
              <div className="review-detail-footer">
                <button className="review-footer-btn">
                  <SkipBack size={11} />
                  Export
                </button>
                <button className="review-footer-btn primary">
                  <CheckCircle size={11} />
                  Send Telegram
                </button>
              </div>
            </>
          ) : (
            <div style={{
              flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
              color: "var(--text-4)", fontSize: 13,
            }}>
              No clip selected
            </div>
          )}
        </div>

      </div>

      {/* Bulk action floating bar */}
      <BulkActions selectedIds={selectedClips} onClear={clearSelection} />
    </>
  );
}
