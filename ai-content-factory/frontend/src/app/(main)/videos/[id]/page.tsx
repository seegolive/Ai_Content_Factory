"use client";
import { use, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Loader2, AlertTriangle, AlertCircle, Layers, Clock, FileVideo,
  Play, TrendingUp, CheckCircle, XCircle, Upload, ExternalLink,
} from "lucide-react";
import { Header } from "@/components/layout/Header";
import { useVideo, useClips, useReviewClip } from "@/lib/queries";
import { formatDuration, formatRelativeTime } from "@/lib/utils";
import type { Clip } from "@/types";
import { clipsApi } from "@/lib/api";
import { toast } from "sonner";

const STATUS_MAP: Record<string, { dot: string; label: string; bg: string }> = {
  processing: { dot: "var(--primary)",   label: "Processing", bg: "var(--primary-dim)" },
  review:     { dot: "var(--warning)",   label: "Review",     bg: "var(--warning-dim)" },
  done:       { dot: "var(--secondary)", label: "Done",       bg: "var(--secondary-dim)" },
  error:      { dot: "var(--danger)",    label: "Error",      bg: "var(--danger-dim)" },
  queued:     { dot: "var(--text-3)",    label: "Queued",     bg: "rgba(255,255,255,0.04)" },
};

function viralClass(score?: number) {
  if (!score) return "low";
  if (score >= 75) return "high";
  if (score >= 50) return "mid";
  return "low";
}

/** Left-panel video player — streams the vertical (9:16) clip format */
function MainPlayer({ clip }: { clip: Clip | null }) {
  const [streamUrl, setStreamUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!clip?.clip_path && !clip?.clip_path_vertical) { setStreamUrl(null); return; }
    let cancelled = false;
    setStreamUrl(null);
    clipsApi.getStreamToken(clip.id)
      .then((res) => {
        if (!cancelled) setStreamUrl(clipsApi.streamUrl(clip.id, res.data.token, "vertical"));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [clip?.id]);

  if (!clip) {
    return (
      <div className="vd-player-empty">
        <Play size={40} color="var(--text-4)" />
        <span style={{ fontSize: 13, color: "var(--text-4)", marginTop: 12 }}>
          Select a clip to preview
        </span>
      </div>
    );
  }

  if (!streamUrl) {
    return (
      <div className="vd-player-empty">
        <Loader2 size={28} color="var(--primary)" className="spin" />
      </div>
    );
  }

  return (
    <video
      key={streamUrl}
      src={streamUrl}
      controls
      autoPlay
      playsInline
      className="vd-player-video"
    />
  );
}

/** Right-panel clip row — 9:16 thumbnail + info */
function ClipRow({
  clip, isActive, onClick,
}: {
  clip: Clip;
  isActive: boolean;
  onClick: () => void;
}) {
  const [thumbUrl, setThumbUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!clip.clip_path) return;
    let cancelled = false;
    clipsApi.getStreamToken(clip.id)
      .then((res) => { if (!cancelled) setThumbUrl(clipsApi.streamUrl(clip.id, res.data.token)); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [clip.id, clip.clip_path]);

  const reviewIcon =
    clip.review_status === "approved" ? (
      <span style={{ color: "var(--secondary)", fontSize: 10, fontFamily: "var(--font-mono)" }}>✓ approved</span>
    ) : clip.review_status === "rejected" ? (
      <span style={{ color: "var(--danger)", fontSize: 10, fontFamily: "var(--font-mono)" }}>✗ rejected</span>
    ) : null;

  return (
    <button
      className={`vd-clip-row${isActive ? " active" : ""}`}
      onClick={onClick}
    >
      {/* 9:16 thumbnail */}
      <div className="vd-clip-thumb">
        {clip.clip_path ? (
          <video src={thumbUrl ?? undefined} muted preload="metadata" />
        ) : (
          <Play size={16} color="var(--text-4)" />
        )}
        {isActive && (
          <div className="vd-clip-thumb-overlay">
            <Play size={18} color="#fff" fill="#fff" />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="vd-clip-info">
        <div className="vd-clip-title">{clip.title ?? "Untitled Clip"}</div>
        <div className="vd-clip-meta">
          <span>{formatDuration(clip.duration)}</span>
          {clip.viral_score != null && (
            <span className={`vd-clip-score ${viralClass(clip.viral_score)}`}>
              <TrendingUp size={9} /> {clip.viral_score}
            </span>
          )}
        </div>
        {reviewIcon && <div style={{ marginTop: 4 }}>{reviewIcon}</div>}
      </div>
    </button>
  );
}

export default function VideoDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data: video, isLoading: videoLoading } = useVideo(id);
  const { data: clips = [], isLoading: clipsLoading } = useClips(id);
  const { mutateAsync: reviewClip } = useReviewClip();
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null);

  const activeClip = clips.find((c) => c.id === selectedClipId) ?? clips[0] ?? null;

  // Auto-select first clip when clips load
  useEffect(() => {
    if (!selectedClipId && clips.length > 0) setSelectedClipId(clips[0].id);
  }, [clips, selectedClipId]);

  const handleReview = async (action: "approve" | "reject") => {
    if (!activeClip) return;
    try {
      await reviewClip({ clipId: activeClip.id, action });
      toast.success(action === "approve" ? "Clip approved!" : "Clip rejected");
    } catch {
      toast.error("Failed to update clip");
    }
  };

  if (videoLoading) {
    return (
      <>
        <Header breadcrumb={[{ label: "Videos", href: "/videos" }, { label: "…" }]} />
        <div className="page-scroll">
          <div className="page-body">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "80px 0" }}>
              <Loader2 size={28} color="var(--primary)" className="spin" />
            </div>
          </div>
        </div>
      </>
    );
  }

  if (!video) return null;

  const s = STATUS_MAP[video.status] ?? STATUS_MAP.queued;
  const pendingCount = clips.filter((c) => c.review_status === "pending").length;

  return (
    <>
      <Header
        breadcrumb={[{ label: "Videos", href: "/videos" }, { label: video.title ?? "Video" }]}
        actions={
          pendingCount > 0 ? (
            <button
              className="btn-primary"
              style={{ height: 28, padding: "0 12px", fontSize: 11 }}
              onClick={() => router.push("/review")}
            >
              Review {pendingCount} clip{pendingCount !== 1 ? "s" : ""} →
            </button>
          ) : undefined
        }
      />

      {/* Full-height split shell */}
      <div className="vd-shell">

        {/* ─── LEFT: player + info ─────────────────────────────── */}
        <div className="vd-left">
          {/* Player area */}
          <div className="vd-player-wrap">
            <MainPlayer clip={activeClip} />
          </div>

          {/* Info below player */}
          <div className="vd-info">
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 10 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <h1 className="vd-title">{video.title ?? "Untitled Video"}</h1>
                <div className="vd-meta">
                  {video.duration_seconds && (
                    <span><Clock size={10} /> {formatDuration(video.duration_seconds)}</span>
                  )}
                  {video.file_size_mb && (
                    <span>
                      <FileVideo size={10} />
                      {video.file_size_mb < 1024
                        ? `${video.file_size_mb.toFixed(1)} MB`
                        : `${(video.file_size_mb / 1024).toFixed(2)} GB`}
                    </span>
                  )}
                  <span><Layers size={10} /> {clips.length} clip{clips.length !== 1 ? "s" : ""}</span>
                  <span>{formatRelativeTime(video.created_at)}</span>
                </div>
              </div>
              <div className="status-pill" style={{ background: s.bg, flexShrink: 0 }}>
                <div className="status-dot" style={{ background: s.dot }} />
                <span style={{ color: s.dot }}>{s.label}</span>
              </div>
            </div>

            {video.error_message && (
              <div className="video-detail-error">
                <AlertCircle size={12} style={{ display: "inline", marginRight: 6 }} />
                {video.error_message}
              </div>
            )}

            {video.copyright_status === "flagged" && (
              <div className="video-detail-error" style={{ color: "var(--warning)", borderColor: "var(--warning-dim)" }}>
                <AlertTriangle size={12} style={{ display: "inline", marginRight: 6 }} />
                Copyright flagged
              </div>
            )}

            {/* Active clip actions */}
            {activeClip && (
              <div style={{ marginTop: 16, padding: "14px 0 0", borderTop: "1px solid var(--border-1)" }}>
                <div style={{ fontSize: 11, color: "var(--text-3)", fontFamily: "var(--font-mono)", marginBottom: 10 }}>
                  Now previewing: <span style={{ color: "var(--text-2)" }}>{activeClip.title ?? "Untitled Clip"}</span>
                </div>
                {activeClip.review_status === "pending" && (
                  <div style={{ display: "flex", gap: 8 }}>
                    <button className="btn-primary" style={{ flex: 1 }} onClick={() => handleReview("approve")}>
                      <CheckCircle size={13} /> Approve
                    </button>
                    <button
                      className="btn-ghost"
                      style={{ flex: 1, color: "var(--danger)", borderColor: "var(--danger-dim)" }}
                      onClick={() => handleReview("reject")}
                    >
                      <XCircle size={13} /> Reject
                    </button>
                  </div>
                )}
                {activeClip.review_status === "approved" && (
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      className="btn-primary"
                      style={{ flex: 1 }}
                      onClick={() => router.push(`/publish/${activeClip.id}`)}
                    >
                      <Upload size={13} /> Publish to YouTube
                    </button>
                    <button
                      className="btn-ghost"
                      style={{ color: "var(--danger)", borderColor: "var(--danger-dim)" }}
                      onClick={() => handleReview("reject")}
                    >
                      <XCircle size={13} /> Reject
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ─── RIGHT: clips panel ──────────────────────────────── */}
        <div className="vd-right">
          <div className="vd-right-hd">
            <span className="vd-right-title">Clips</span>
            {!clipsLoading && (
              <span className="vd-right-count">{clips.length} total</span>
            )}
          </div>

          <div className="vd-clips-list">
            {clipsLoading ? (
              <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
                <Loader2 size={24} color="var(--primary)" className="spin" />
              </div>
            ) : clips.length === 0 ? (
              <div style={{ padding: "48px 20px", textAlign: "center" }}>
                <Layers size={28} color="var(--text-4)" style={{ margin: "0 auto 12px" }} />
                <div style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 6 }}>
                  No clips yet
                </div>
                <div style={{ fontSize: 12, color: "var(--text-4)" }}>
                  {video.status === "processing"
                    ? "Clips will appear once the AI pipeline finishes."
                    : "This video hasn't been processed yet."}
                </div>
              </div>
            ) : (
              clips.map((clip) => (
                <ClipRow
                  key={clip.id}
                  clip={clip}
                  isActive={clip.id === (activeClip?.id)}
                  onClick={() => setSelectedClipId(clip.id)}
                />
              ))
            )}
          </div>
        </div>

      </div>
    </>
  );
}
