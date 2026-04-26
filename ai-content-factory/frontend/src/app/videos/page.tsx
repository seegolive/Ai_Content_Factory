"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { VideoUploader } from "@/components/video/VideoUploader";
import { VideoCard } from "@/components/video/VideoCard";
import { useVideos } from "@/lib/queries";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

const STATUS_FILTERS = ["all", "queued", "processing", "review", "done", "error"] as const;

export default function VideosPage() {
  const router = useRouter();
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const { data: videos = [], isLoading } = useVideos(
    statusFilter !== "all" ? { status: statusFilter } : undefined
  );

  return (
    <div className="flex flex-col flex-1">
      <Header breadcrumb={[{ label: "Videos" }]} />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto">
        {/* Upload */}
        <VideoUploader onSuccess={(id) => router.push(`/videos/${id}`)} />

        {/* Filters */}
        <div className="flex items-center gap-2 flex-wrap">
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={cn(
                "px-3 py-1.5 text-xs rounded-lg font-medium transition-all capitalize",
                statusFilter === s
                  ? "bg-primary text-white"
                  : "text-foreground-muted hover:text-foreground hover:bg-muted/50"
              )}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Video Grid */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-primary animate-spin" />
          </div>
        ) : videos.length === 0 ? (
          <div className="text-center py-20 text-foreground-muted text-sm">
            No videos found.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {videos.map((v) => (
              <VideoCard key={v.id} video={v} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
