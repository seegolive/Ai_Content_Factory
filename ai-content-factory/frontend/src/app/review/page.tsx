"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  CheckCircle,
  XCircle,
  ChevronLeft,
  ChevronRight,
  Play,
  Pause,
  TrendingUp,
  AlertTriangle,
  Edit2,
  Check,
} from "lucide-react";
import { Header } from "@/components/layout/Header";
import { BulkActions } from "@/components/clips/BulkActions";
import { useVideos, useClips, useReviewClip, useUpdateClip } from "@/lib/queries";
import { useUIStore } from "@/stores/uiStore";
import { clipsApi } from "@/lib/api";
import { cn, formatDuration, getStatusColor, getViralScoreColor } from "@/lib/utils";
import { toast } from "sonner";
import type { Clip } from "@/types";

export default function ReviewPage() {
  const { selectedClips, toggleClipSelection, clearSelection } = useUIStore();
  const { reviewActiveClipId, setReviewActiveClip } = useUIStore();

  // Get all videos with review status
  const { data: reviewVideos = [] } = useVideos({ status: "review" });
  const firstVideoId = reviewVideos[0]?.id ?? "";

  const { data: clips = [] } = useClips(firstVideoId);
  const pendingClips = clips.filter((c) => c.review_status === "pending");

  const activeClip = pendingClips.find((c) => c.id === reviewActiveClipId) ?? pendingClips[0];

  const { mutateAsync: reviewClip } = useReviewClip();
  const { mutateAsync: updateClip } = useUpdateClip();

  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");

  // Set first clip as active initially
  useEffect(() => {
    if (!reviewActiveClipId && pendingClips.length > 0) {
      setReviewActiveClip(pendingClips[0].id);
    }
  }, [pendingClips.length]);

  // Keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!activeClip || editingTitle) return;
      const idx = pendingClips.findIndex((c) => c.id === activeClip.id);

      switch (e.key.toLowerCase()) {
        case "a":
          e.preventDefault();
          handleReview("approve");
          break;
        case "r":
          e.preventDefault();
          handleReview("reject");
          break;
        case "j":
        case "arrowdown":
          if (idx < pendingClips.length - 1) setReviewActiveClip(pendingClips[idx + 1].id);
          break;
        case "k":
        case "arrowup":
          if (idx > 0) setReviewActiveClip(pendingClips[idx - 1].id);
          break;
        case " ":
          e.preventDefault();
          togglePlay();
          break;
        case "b":
          e.preventDefault();
          toggleClipSelection(activeClip.id);
          break;
      }
    },
    [activeClip, pendingClips, editingTitle]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play();
      setIsPlaying(true);
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  };

  const handleReview = async (action: "approve" | "reject") => {
    if (!activeClip) return;
    try {
      await reviewClip({ clipId: activeClip.id, action });
      toast.success(action === "approve" ? "✅ Approved" : "❌ Rejected");
      // Move to next clip
      const idx = pendingClips.findIndex((c) => c.id === activeClip.id);
      if (idx < pendingClips.length - 1) {
        setReviewActiveClip(pendingClips[idx + 1].id);
      }
    } catch {
      toast.error("Action failed");
    }
  };

  const handleSaveTitle = async () => {
    if (!activeClip || !titleDraft.trim()) return;
    await updateClip({ clipId: activeClip.id, data: { title: titleDraft } });
    setEditingTitle(false);
    toast.success("Title updated");
  };

  return (
    <div className="flex flex-col flex-1 h-screen overflow-hidden">
      <Header breadcrumb={[{ label: "Review Queue" }]} />

      {pendingClips.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-foreground-muted text-sm">
          No clips pending review.
        </div>
      ) : (
        <div className="flex flex-1 overflow-hidden">
          {/* Left panel — clip list */}
          <div className="w-80 flex-shrink-0 border-r border-border flex flex-col overflow-hidden">
            <div className="px-4 py-3 border-b border-border flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">
                {pendingClips.length} pending
              </span>
              {selectedClips.length > 0 && (
                <button
                  onClick={clearSelection}
                  className="text-xs text-foreground-muted hover:text-foreground"
                >
                  Clear
                </button>
              )}
            </div>
            <div className="flex-1 overflow-y-auto">
              {pendingClips.map((clip, idx) => (
                <div
                  key={clip.id}
                  onClick={() => setReviewActiveClip(clip.id)}
                  className={cn(
                    "flex items-center gap-3 px-4 py-3 cursor-pointer border-b border-border/50 transition-colors",
                    clip.id === activeClip?.id
                      ? "bg-primary/10 border-l-2 border-l-primary"
                      : "hover:bg-muted/30"
                  )}
                >
                  <input
                    type="checkbox"
                    checked={selectedClips.includes(clip.id)}
                    onChange={(e) => {
                      e.stopPropagation();
                      toggleClipSelection(clip.id);
                    }}
                    onClick={(e) => e.stopPropagation()}
                    className="rounded border-border bg-muted"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-foreground truncate">
                      {clip.title ?? `Clip ${idx + 1}`}
                    </p>
                    {clip.viral_score !== undefined && (
                      <span
                        className={cn(
                          "text-xs font-mono flex items-center gap-1",
                          getViralScoreColor(clip.viral_score)
                        )}
                      >
                        <TrendingUp className="w-2.5 h-2.5" />
                        {clip.viral_score}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right panel */}
          {activeClip && (
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Video player */}
              <div className="relative bg-black aspect-video flex-shrink-0">
                <video
                  ref={videoRef}
                  key={activeClip.id}
                  src={clipsApi.streamUrl(activeClip.id)}
                  className="w-full h-full object-contain"
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  loop
                />
                <button
                  onClick={togglePlay}
                  className="absolute inset-0 flex items-center justify-center text-white opacity-0 hover:opacity-100 transition-opacity bg-black/20"
                >
                  {isPlaying ? <Pause className="w-12 h-12" /> : <Play className="w-12 h-12" />}
                </button>
              </div>

              {/* Clip details + actions */}
              <div className="flex-1 overflow-y-auto p-5 space-y-4">
                {/* Title */}
                <div className="flex items-start gap-2">
                  {editingTitle ? (
                    <div className="flex-1 flex gap-2">
                      <input
                        autoFocus
                        value={titleDraft}
                        onChange={(e) => setTitleDraft(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleSaveTitle()}
                        className="flex-1 bg-muted border border-primary rounded-lg px-3 py-1.5 text-sm text-foreground focus:outline-none"
                      />
                      <button
                        onClick={handleSaveTitle}
                        className="p-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20"
                      >
                        <Check className="w-4 h-4" />
                      </button>
                    </div>
                  ) : (
                    <>
                      <h2 className="flex-1 text-base font-display font-semibold text-foreground leading-snug">
                        {activeClip.title ?? "Untitled Clip"}
                      </h2>
                      <button
                        onClick={() => {
                          setTitleDraft(activeClip.title ?? "");
                          setEditingTitle(true);
                        }}
                        className="p-1.5 rounded-lg text-foreground-muted hover:text-foreground hover:bg-muted/50 transition-colors flex-shrink-0"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                    </>
                  )}
                </div>

                {/* Viral score + hook */}
                {activeClip.viral_score !== undefined && (
                  <div className="glass-card p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <TrendingUp className={cn("w-4 h-4", getViralScoreColor(activeClip.viral_score))} />
                      <span className={cn("font-mono font-bold text-sm", getViralScoreColor(activeClip.viral_score))}>
                        Viral Score: {activeClip.viral_score}/100
                      </span>
                    </div>
                    {activeClip.hook_text && (
                      <p className="text-sm text-foreground-muted italic">"{activeClip.hook_text}"</p>
                    )}
                  </div>
                )}

                {/* QC Issues */}
                {activeClip.qc_issues.length > 0 && (
                  <div className="glass-card p-3 border-warning/30">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertTriangle className="w-4 h-4 text-warning" />
                      <span className="text-xs font-medium text-warning">QC Issues</span>
                    </div>
                    {activeClip.qc_issues.map((issue, i) => (
                      <p key={i} className="text-xs text-foreground-muted">
                        • {issue.description}
                      </p>
                    ))}
                  </div>
                )}

                {/* Hashtags */}
                {activeClip.hashtags.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {activeClip.hashtags.map((tag) => (
                      <span key={tag} className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                        #{tag}
                      </span>
                    ))}
                  </div>
                )}

                {/* Duration */}
                <p className="text-xs text-foreground-muted font-mono">
                  {formatDuration(activeClip.start_time)} → {formatDuration(activeClip.end_time)} ({formatDuration(activeClip.duration)})
                </p>
              </div>

              {/* Action bar (sticky bottom) */}
              <div className="flex-shrink-0 p-4 border-t border-border bg-surface/80 backdrop-blur-sm">
                <div className="flex items-center gap-3">
                  <div className="text-xs text-foreground-muted">
                    <kbd className="px-1.5 py-0.5 bg-muted rounded text-xs">A</kbd> Approve ·{" "}
                    <kbd className="px-1.5 py-0.5 bg-muted rounded text-xs">R</kbd> Reject ·{" "}
                    <kbd className="px-1.5 py-0.5 bg-muted rounded text-xs">J/K</kbd> Navigate ·{" "}
                    <kbd className="px-1.5 py-0.5 bg-muted rounded text-xs">Space</kbd> Play
                  </div>
                  <div className="ml-auto flex gap-2">
                    <button
                      onClick={() => handleReview("reject")}
                      className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-destructive/10 text-destructive hover:bg-destructive/20 font-medium text-sm transition-colors"
                    >
                      <XCircle className="w-4 h-4" /> Reject
                    </button>
                    <button
                      onClick={() => handleReview("approve")}
                      className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-secondary text-background hover:bg-secondary/90 font-medium text-sm transition-colors"
                    >
                      <CheckCircle className="w-4 h-4" /> Approve
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <BulkActions selectedIds={selectedClips} onClear={clearSelection} />
    </div>
  );
}
