"use client";
import { useRouter } from "next/navigation";
import {
  Video,
  Scissors,
  Clock,
  Upload,
  TrendingUp,
  CheckCircle,
  AlertCircle,
  Loader2,
  ChevronRight,
} from "lucide-react";
import { Header } from "@/components/layout/Header";
import { useVideos, useClips, useVideoStatus } from "@/lib/queries";
import { cn, formatRelativeTime, getStatusColor } from "@/lib/utils";

function StatCard({
  label,
  value,
  icon: Icon,
  color = "primary",
}: {
  label: string;
  value: number | string;
  icon: React.ElementType;
  color?: "primary" | "secondary" | "accent" | "warning";
}) {
  const colorMap = {
    primary: "text-primary bg-primary/10",
    secondary: "text-secondary bg-secondary/10",
    accent: "text-accent bg-accent/10",
    warning: "text-warning bg-warning/10",
  };
  return (
    <div className="glass-card p-5 flex items-start gap-4">
      <div className={cn("p-2.5 rounded-lg flex-shrink-0", colorMap[color])}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-2xl font-display font-bold text-foreground">{value}</p>
        <p className="text-sm text-foreground-muted mt-0.5">{label}</p>
      </div>
    </div>
  );
}

function ProcessingItem({ videoId }: { videoId: string }) {
  const { data: status } = useVideoStatus(videoId);
  if (!status) return null;

  const stages = [
    "input_validated",
    "transcript_done",
    "ai_done",
    "qc_done",
    "clips_done",
    "review_ready",
  ];
  const stageLabels: Record<string, string> = {
    input_validated: "Validated",
    transcript_done: "Transcribed",
    ai_done: "Analyzed",
    qc_done: "QC Done",
    clips_done: "Processed",
    review_ready: "Ready",
  };

  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-foreground truncate">
          {status.current_stage ? stageLabels[status.current_stage] ?? status.current_stage : "Processing…"}
        </span>
        <span className="text-xs font-mono text-primary">{status.progress_percent}%</span>
      </div>
      <div className="w-full bg-muted rounded-full h-1.5">
        <div
          className="bg-primary h-1.5 rounded-full transition-all duration-500"
          style={{ width: `${status.progress_percent}%` }}
        />
      </div>
      <div className="flex gap-1 mt-3">
        {stages.map((stage) => {
          const idx = stages.indexOf(stage);
          const currentIdx = stages.indexOf(status.current_stage ?? "");
          const done = currentIdx > idx;
          const active = currentIdx === idx;
          return (
            <div
              key={stage}
              className={cn(
                "flex-1 h-1 rounded-full",
                done ? "bg-secondary" : active ? "bg-primary animate-pulse" : "bg-muted"
              )}
            />
          );
        })}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const { data: allVideos = [] } = useVideos();
  const { data: processingVideos = [] } = useVideos({ status: "processing" });
  const { data: reviewVideos = [] } = useVideos({ status: "review" });
  const { data: doneVideos = [] } = useVideos({ status: "done" });

  const totalClips = allVideos.reduce((sum, v) => sum + v.clips_count, 0);
  const pendingReview = reviewVideos.reduce((sum, v) => sum + v.clips_count, 0);

  return (
    <div className="flex flex-col flex-1">
      <Header breadcrumb={[{ label: "Dashboard" }]} />

      <div className="flex-1 p-6 space-y-6 overflow-y-auto">
        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Total Videos" value={allVideos.length} icon={Video} color="primary" />
          <StatCard label="Clips Generated" value={totalClips} icon={Scissors} color="secondary" />
          <StatCard label="Pending Review" value={pendingReview} icon={Clock} color="warning" />
          <StatCard label="Published" value={doneVideos.length} icon={CheckCircle} color="accent" />
        </div>

        {/* Processing Jobs */}
        {processingVideos.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Loader2 className="w-4 h-4 text-primary animate-spin" />
              <h2 className="text-sm font-semibold text-foreground">
                Active Jobs ({processingVideos.length})
              </h2>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {processingVideos.map((v) => (
                <ProcessingItem key={v.id} videoId={v.id} />
              ))}
            </div>
          </section>
        )}

        {/* Review Queue quick access */}
        {reviewVideos.length > 0 && (
          <section>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-foreground">Review Queue</h2>
              <button
                onClick={() => router.push("/review")}
                className="text-xs text-primary hover:underline flex items-center gap-1"
              >
                View all <ChevronRight className="w-3 h-3" />
              </button>
            </div>
            <div className="glass-card divide-y divide-border">
              {reviewVideos.slice(0, 5).map((v) => (
                <div
                  key={v.id}
                  onClick={() => router.push(`/videos/${v.id}`)}
                  className="flex items-center justify-between px-4 py-3 hover:bg-muted/30 cursor-pointer transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {v.title ?? "Untitled"}
                    </p>
                    <p className="text-xs text-foreground-muted">{v.clips_count} clips ready</p>
                  </div>
                  <span
                    className={cn(
                      "text-xs px-2 py-1 rounded-full font-medium ml-3",
                      getStatusColor(v.status)
                    )}
                  >
                    {v.status}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Recent Videos */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-foreground">Recent Videos</h2>
            <button
              onClick={() => router.push("/videos")}
              className="text-xs text-primary hover:underline flex items-center gap-1"
            >
              View all <ChevronRight className="w-3 h-3" />
            </button>
          </div>
          {allVideos.length === 0 ? (
            <div className="glass-card p-12 text-center">
              <Upload className="w-10 h-10 text-foreground-muted mx-auto mb-3" />
              <p className="text-foreground-muted text-sm">No videos yet.</p>
              <button
                onClick={() => router.push("/videos")}
                className="mt-3 px-4 py-2 bg-primary text-white text-sm rounded-lg hover:bg-primary/90 transition-colors"
              >
                Upload your first video
              </button>
            </div>
          ) : (
            <div className="glass-card divide-y divide-border">
              {allVideos.slice(0, 5).map((v) => (
                <div
                  key={v.id}
                  onClick={() => router.push(`/videos/${v.id}`)}
                  className="flex items-center justify-between px-4 py-3 hover:bg-muted/30 cursor-pointer transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {v.title ?? "Untitled"}
                    </p>
                    <p className="text-xs text-foreground-muted">
                      {formatRelativeTime(v.created_at)} · {v.clips_count} clips
                    </p>
                  </div>
                  <span
                    className={cn(
                      "text-xs px-2 py-1 rounded-full font-medium ml-3",
                      getStatusColor(v.status)
                    )}
                  >
                    {v.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
