"use client";
import { use } from "react";
import { useRouter } from "next/navigation";
import { Loader2, AlertTriangle, AlertCircle, Layers, Clock, FileVideo } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { useVideo, useClips } from "@/lib/queries";
import { ClipCard } from "@/components/clips/ClipCard";
import { formatDuration, formatRelativeTime } from "@/lib/utils";

const STATUS_MAP: Record<string, { dot: string; label: string; bg: string }> = {
  processing: { dot: "var(--primary)",   label: "Processing", bg: "var(--primary-dim)" },
  review:     { dot: "var(--warning)",   label: "Review",     bg: "var(--warning-dim)" },
  done:       { dot: "var(--secondary)", label: "Done",       bg: "var(--secondary-dim)" },
  error:      { dot: "var(--danger)",    label: "Error",      bg: "var(--danger-dim)" },
  queued:     { dot: "var(--text-3)",    label: "Queued",     bg: "rgba(255,255,255,0.04)" },
};

export default function VideoDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data: video, isLoading: videoLoading } = useVideo(id);
  const { data: clips = [], isLoading: clipsLoading } = useClips(id);

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
  const approvedCount = clips.filter((c) => c.review_status === "approved").length;

  return (
    <>
      <Header
        breadcrumb={[
          { label: "Videos", href: "/videos" },
          { label: video.title ?? "Video" },
        ]}
      />

      <div className="page-scroll">
        <div className="page-body">

          {/* Video info card */}
          <div className="video-detail-info anim-0">
            <div className="video-detail-header">
              <div style={{ flex: 1, minWidth: 0 }}>
                <h1 className="video-detail-title">{video.title ?? "Untitled Video"}</h1>
                <div className="video-detail-meta">
                  {video.duration_seconds && (
                    <>
                      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <Clock size={10} />
                        {formatDuration(video.duration_seconds)}
                      </span>
                      <span className="video-detail-dot">·</span>
                    </>
                  )}
                  {video.file_size_mb && (
                    <>
                      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <FileVideo size={10} />
                        {video.file_size_mb < 1024
                          ? `${video.file_size_mb.toFixed(1)} MB`
                          : `${(video.file_size_mb / 1024).toFixed(2)} GB`}
                      </span>
                      <span className="video-detail-dot">·</span>
                    </>
                  )}
                  <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <Layers size={10} />
                    {clips.length} clip{clips.length !== 1 ? "s" : ""}
                  </span>
                  <span className="video-detail-dot">·</span>
                  <span>{formatRelativeTime(video.created_at)}</span>
                  {video.copyright_status === "flagged" && (
                    <>
                      <span className="video-detail-dot">·</span>
                      <span className="video-detail-copyright-warn">
                        <AlertTriangle size={10} /> Copyright flagged
                      </span>
                    </>
                  )}
                </div>
              </div>

              {/* Status badge */}
              <div
                className="status-pill"
                style={{ background: s.bg, flexShrink: 0 }}
              >
                <div className="status-dot" style={{ background: s.dot }} />
                <span style={{ color: s.dot }}>{s.label}</span>
              </div>
            </div>

            {/* Error message */}
            {video.error_message && (
              <div className="video-detail-error">
                <AlertCircle size={12} style={{ display: "inline", marginRight: 6 }} />
                {video.error_message}
              </div>
            )}

            {/* Clip summary chips */}
            {clips.length > 0 && (
              <div style={{ display: "flex", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
                {pendingCount > 0 && (
                  <div className="status-pill" style={{ background: "var(--warning-dim)" }}>
                    <div className="status-dot" style={{ background: "var(--warning)" }} />
                    <span style={{ color: "var(--warning)" }}>{pendingCount} pending</span>
                  </div>
                )}
                {approvedCount > 0 && (
                  <div className="status-pill" style={{ background: "var(--secondary-dim)" }}>
                    <div className="status-dot" style={{ background: "var(--secondary)" }} />
                    <span style={{ color: "var(--secondary)" }}>{approvedCount} approved</span>
                  </div>
                )}
                {pendingCount > 0 && (
                  <button
                    className="btn-primary"
                    style={{ height: 26, padding: "0 12px", fontSize: 11 }}
                    onClick={() => router.push("/review")}
                  >
                    Review Clips →
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Clips section */}
          <div className="anim-1">
            <div className="clips-section-hd" style={{ marginBottom: 12 }}>
              <span className="clips-section-title">Clips</span>
              {!clipsLoading && (
                <span className="clips-section-count">{clips.length} total</span>
              )}
            </div>

            {clipsLoading ? (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "60px 0" }}>
                <Loader2 size={24} color="var(--primary)" className="spin" />
              </div>
            ) : clips.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">
                  <Layers size={20} color="var(--text-4)" />
                </div>
                <div className="empty-title">No clips generated yet</div>
                <div className="empty-desc">
                  {video.status === "processing"
                    ? "Clips will appear here once the AI pipeline finishes processing."
                    : "This video has not been through the pipeline yet."}
                </div>
              </div>
            ) : (
              <div className="clips-grid">
                {clips.map((clip) => (
                  <ClipCard key={clip.id} clip={clip} showActions />
                ))}
              </div>
            )}
          </div>

        </div>
      </div>
    </>
  );
}
