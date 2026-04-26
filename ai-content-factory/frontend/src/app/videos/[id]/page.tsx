"use client";
import { use } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { useVideo, useClips } from "@/lib/queries";
import { ClipCard } from "@/components/clips/ClipCard";
import { cn, formatDuration, getStatusColor } from "@/lib/utils";

export default function VideoDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data: video, isLoading: videoLoading } = useVideo(id);
  const { data: clips = [], isLoading: clipsLoading } = useClips(id);

  if (videoLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  if (!video) return null;

  return (
    <div className="flex flex-col flex-1">
      <Header
        breadcrumb={[
          { label: "Videos", href: "/videos" },
          { label: video.title ?? "Video" },
        ]}
      />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto">
        {/* Video info */}
        <div className="glass-card p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-lg font-display font-semibold text-foreground">
                {video.title ?? "Untitled"}
              </h1>
              <div className="flex items-center gap-3 mt-2 text-sm text-foreground-muted">
                <span>{formatDuration(video.duration_seconds)}</span>
                <span>·</span>
                <span>{clips.length} clips</span>
                {video.copyright_status === "flagged" && (
                  <>
                    <span>·</span>
                    <span className="text-destructive">⚠ Copyright flagged</span>
                  </>
                )}
              </div>
            </div>
            <span
              className={cn(
                "text-xs px-2.5 py-1 rounded-full font-medium",
                getStatusColor(video.status)
              )}
            >
              {video.status}
            </span>
          </div>
          {video.error_message && (
            <p className="mt-3 text-xs text-destructive bg-destructive/10 px-3 py-2 rounded-lg">
              {video.error_message}
            </p>
          )}
        </div>

        {/* Clips */}
        <div>
          <h2 className="text-sm font-semibold text-foreground mb-3">
            Clips ({clips.length})
          </h2>
          {clipsLoading ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="w-6 h-6 text-primary animate-spin" />
            </div>
          ) : clips.length === 0 ? (
            <div className="glass-card p-10 text-center text-foreground-muted text-sm">
              No clips generated yet.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {clips.map((clip) => (
                <ClipCard key={clip.id} clip={clip} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
