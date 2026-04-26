"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { VideoUploader } from "@/components/video/VideoUploader";
import { VideoCard } from "@/components/video/VideoCard";
import { useVideos } from "@/lib/queries";
import { Upload, Loader2 } from "lucide-react";

const STATUS_FILTERS = ["all", "queued", "processing", "review", "done", "error"] as const;

export default function VideosPage() {
  const router = useRouter();
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showUploader, setShowUploader] = useState(false);

  const { data: videos = [], isLoading } = useVideos(
    statusFilter !== "all" ? { status: statusFilter } : undefined
  );

  return (
    <>
      <Header
        breadcrumb={[{ label: "Videos" }]}
        actions={
          <button className="btn-primary" onClick={() => setShowUploader(!showUploader)}>
            <Upload size={13} />
            Upload Video
          </button>
        }
      />

      <div className="page-scroll">
        <div className="page-body">

          {/* Inline uploader panel — toggles open */}
          {showUploader && (
            <div className="anim-0">
              <VideoUploader onSuccess={(id) => { setShowUploader(false); router.push(`/videos/${id}`); }} />
            </div>
          )}

          {/* Filter row */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
            <div className="filter-tabs">
              {STATUS_FILTERS.map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={`filter-tab${statusFilter === s ? " active" : ""}`}
                >
                  {s}
                </button>
              ))}
            </div>
            <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--text-4)" }}>
              {!isLoading && `${videos.length} video${videos.length !== 1 ? "s" : ""}`}
            </span>
          </div>

          {/* Grid */}
          {isLoading ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "80px 0" }}>
              <Loader2 size={28} color="var(--primary)" className="spin" />
            </div>
          ) : videos.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">
                <Upload size={20} color="var(--primary-text)" />
              </div>
              <div className="empty-title">
                {statusFilter === "all" ? "No videos yet" : `No ${statusFilter} videos`}
              </div>
              <div className="empty-desc">
                {statusFilter === "all"
                  ? "Upload your first long-form video to start the AI pipeline."
                  : "Try a different status filter."}
              </div>
              {statusFilter === "all" && (
                <button className="btn-primary" onClick={() => setShowUploader(true)}>
                  <Upload size={13} /> Upload Video
                </button>
              )}
            </div>
          ) : (
            <div className="video-grid">
              {videos.map((v) => (
                <VideoCard key={v.id} video={v} />
              ))}
            </div>
          )}

        </div>
      </div>
    </>
  );
}

