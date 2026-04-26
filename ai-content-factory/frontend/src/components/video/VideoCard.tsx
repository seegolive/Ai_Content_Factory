"use client";
import { useRouter } from "next/navigation";
import { MoreVertical, Trash2, RefreshCw, Eye } from "lucide-react";
import { cn, formatDuration, formatFileSize, formatRelativeTime, getStatusColor } from "@/lib/utils";
import { useDeleteVideo } from "@/lib/queries";
import { toast } from "sonner";
import type { Video } from "@/types";

interface VideoCardProps {
  video: Video;
}

export function VideoCard({ video }: VideoCardProps) {
  const router = useRouter();
  const { mutateAsync: deleteVideo } = useDeleteVideo();

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

  return (
    <div
      onClick={() => router.push(`/videos/${video.id}`)}
      className="glass-card p-4 cursor-pointer hover:border-primary/30 transition-all duration-200 group"
    >
      {/* Thumbnail placeholder */}
      <div className="w-full aspect-video bg-muted rounded-lg mb-3 flex items-center justify-center overflow-hidden">
        <div className="text-foreground-muted text-xs">No preview</div>
      </div>

      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground truncate">
            {video.title ?? "Untitled"}
          </p>
          <p className="text-xs text-foreground-muted mt-0.5">
            {formatRelativeTime(video.created_at)} ·{" "}
            {formatDuration(video.duration_seconds)} ·{" "}
            {video.clips_count} clips
          </p>
        </div>

        <span
          className={cn(
            "flex-shrink-0 text-xs px-2 py-1 rounded-full font-medium",
            getStatusColor(video.status)
          )}
        >
          {video.status}
        </span>
      </div>

      {/* Actions */}
      <div className="mt-3 pt-3 border-t border-border flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={(e) => { e.stopPropagation(); router.push(`/videos/${video.id}`); }}
          className="flex items-center gap-1.5 text-xs text-foreground-muted hover:text-foreground px-2 py-1 rounded hover:bg-muted/50 transition-colors"
        >
          <Eye className="w-3 h-3" /> View Clips
        </button>
        <button
          onClick={handleDelete}
          className="flex items-center gap-1.5 text-xs text-destructive hover:text-destructive px-2 py-1 rounded hover:bg-destructive/10 transition-colors ml-auto"
        >
          <Trash2 className="w-3 h-3" /> Delete
        </button>
      </div>
    </div>
  );
}
