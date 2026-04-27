"use client";
import { useRouter } from "next/navigation";
import { Play, Eye, Trash2, Clock, Layers, Download } from "lucide-react";
import { formatDuration, formatRelativeTime } from "@/lib/utils";
import { useDeleteVideo } from "@/lib/queries";
import { toast } from "sonner";
import Image from "next/image";
import type { Video } from "@/types";

const STATUS_MAP: Record<string, { dot: string; label: string; bg: string }> = {
  processing: { dot: "var(--primary)",   label: "Processing", bg: "var(--primary-dim)" },
  review:     { dot: "var(--warning)",   label: "Review",     bg: "var(--warning-dim)" },
  done:       { dot: "var(--secondary)", label: "Done",       bg: "var(--secondary-dim)" },
  error:      { dot: "var(--danger)",    label: "Error",      bg: "var(--danger-dim)" },
  queued:     { dot: "var(--text-3)",    label: "Queued",     bg: "rgba(255,255,255,0.04)" },
};

interface VideoCardProps {
  video: Video;
}

export function VideoCard({ video }: VideoCardProps) {
  const router = useRouter();
  const { mutateAsync: deleteVideo } = useDeleteVideo();
  const s = STATUS_MAP[video.status] ?? STATUS_MAP.queued;

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Delete this video and all its clips?")) return;
    try {
      await deleteVideo(video.id);
      toast.success("Video deleted");
    } catch {
      toast.error("Failed to delete video");
    }
  };

  const isDownloading = video.status === "processing"
    && !video.checkpoint
    && typeof video.download_progress === "number"
    && video.download_progress < 100;

  return (
    <div
      className="video-card"
      role="button"
      tabIndex={0}
      onClick={() => router.push(`/videos/${video.id}`)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          router.push(`/videos/${video.id}`);
        }
      }}
    >
      {/* Thumbnail */}
      <div className="video-card-thumb">
        {video.thumbnail_url ? (
          <Image
            src={video.thumbnail_url}
            alt={video.title ?? "Video thumbnail"}
            fill
            sizes="240px"
            style={{ objectFit: "cover" }}
            unoptimized
          />
        ) : (
          <Play size={18} color="var(--text-4)" />
        )}
        <div
          className="status-pill"
          role="status"
          aria-label={`Status: ${s.label}`}
          style={{
            position: "absolute", top: 8, right: 8,
            background: s.bg, fontSize: 10,
          }}
        >
          <div className="status-dot" style={{ background: s.dot }} />
          <span style={{ color: s.dot }}>{s.label}</span>
        </div>
        {video.quality_preference && (
          <span style={{
            position: "absolute", bottom: 8, left: 8,
            background: "rgba(0,0,0,0.65)", borderRadius: 4,
            fontSize: 9, fontFamily: "var(--font-mono)", padding: "2px 5px",
            color: "var(--text-2)",
          }}>
            {video.quality_preference}
          </span>
        )}
      </div>

      {/* Download progress bar (visible while downloading) */}
      {isDownloading && (
        <div style={{ padding: "6px 12px 0", background: "var(--surface-2)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
            <Download size={10} color="var(--primary-text)" className="spin-slow" />
            <span style={{ fontSize: 10, color: "var(--text-3)" }}>
              Downloading… {video.download_progress}%
            </span>
          </div>
          <div style={{ height: 3, background: "var(--border)", borderRadius: 2, overflow: "hidden" }}>
            <div style={{
              height: "100%", background: "var(--primary)",
              width: `${video.download_progress}%`,
              transition: "width 0.4s ease",
              borderRadius: 2,
            }} />
          </div>
        </div>
      )}

      {/* Body */}
      <div className="video-card-body">
        <div className="video-card-title">{video.title ?? "Untitled"}</div>
        <div className="video-card-meta">
          <Clock size={10} style={{ display: "inline", marginRight: 3 }} />
          {formatDuration(video.duration_seconds)}
          &nbsp;&middot;&nbsp;
          {video.created_at ? formatRelativeTime(video.created_at) : "Unknown"}
        </div>

        <div className="video-card-footer">
          <span style={{
            display: "flex", alignItems: "center", gap: 5,
            fontSize: 12, fontFamily: "var(--font-mono)",
            color: video.clips_count > 0 ? "var(--secondary)" : "var(--text-4)",
          }}>
            <Layers size={11} />
            {video.clips_count} clip{video.clips_count !== 1 && "s"}
          </span>

          <div className="video-card-actions">
            <button
              type="button"
              className="icon-btn"
              onClick={(e) => { e.stopPropagation(); router.push(`/videos/${video.id}`); }}
              title="View clips"
              aria-label="View clips"
            >
              <Eye size={13} />
            </button>
            <button
              type="button"
              className="icon-btn danger"
              onClick={handleDelete}
              title="Delete video"
              aria-label="Delete video"
            >
              <Trash2 size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}


