"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  CheckCircle, XCircle, Play, Pause, TrendingUp, AlertTriangle, Edit2, Check,
} from "lucide-react";
import { Header } from "@/components/layout/Header";
import { useVideos, useClips, useReviewClip, useUpdateClip } from "@/lib/queries";
import { useUIStore } from "@/stores/uiStore";
import { clipsApi } from "@/lib/api";
import { formatDuration } from "@/lib/utils";
import { toast } from "sonner";
import type { Clip } from "@/types";
import { BulkActions } from "@/components/clips/BulkActions";

function viralColor(score: number) {
  if (score >= 75) return "var(--secondary)";
  if (score >= 50) return "var(--warning)";
  return "var(--danger)";
}

export default function ReviewPage() {
  const { selectedClips, toggleClipSelection, clearSelection, reviewActiveClipId, setReviewActiveClip } = useUIStore();

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

  useEffect(() => {
    if (!reviewActiveClipId && pendingClips.length > 0) {
      setReviewActiveClip(pendingClips[0].id);
    }
  }, [pendingClips.length]);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) { videoRef.current.play(); setIsPlaying(true); }
    else { videoRef.current.pause(); setIsPlaying(false); }
  };

  const handleReview = async (action: "approve" | "reject") => {
    if (!activeClip) return;
    try {
      await reviewClip({ clipId: activeClip.id, action });
      toast.success(action === "approve" ? "Approved" : "Rejected");
      const idx = pendingClips.findIndex((c) => c.id === activeClip.id);
      if (idx < pendingClips.length - 1) setReviewActiveClip(pendingClips[idx + 1].id);
    } catch { toast.error("Action failed"); }
  };

  const handleSaveTitle = async () => {
    if (!activeClip || !titleDraft.trim()) return;
    await updateClip({ clipId: activeClip.id, data: { title: titleDraft } });
    setEditingTitle(false);
    toast.success("Title updated");
  };

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!activeClip || editingTitle) return;
    const idx = pendingClips.findIndex((c) => c.id === activeClip.id);
    switch (e.key.toLowerCase()) {
      case "a": e.preventDefault(); handleReview("approve"); break;
      case "r": e.preventDefault(); handleReview("reject"); break;
      case "j": case "arrowdown":
        if (idx < pendingClips.length - 1) setReviewActiveClip(pendingClips[idx + 1].id); break;
      case "k": case "arrowup":
        if (idx > 0) setReviewActiveClip(pendingClips[idx - 1].id); break;
      case " ": e.preventDefault(); togglePlay(); break;
      case "b": e.preventDefault(); toggleClipSelection(activeClip.id); break;
    }
  }, [activeClip, pendingClips, editingTitle]);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return (
    <>
      <Header breadcrumb={[{ label: "Review Queue" }]} />

      {pendingClips.length === 0 ? (
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
      ) : (
        <div className="review-shell">

          {/* Left — clip list */}
          <div className="review-list">
            <div className="review-list-hd">
              <span className="review-list-hd-title">{pendingClips.length} clips pending</span>
              {selectedClips.length > 0 && (
                <button className="btn-link" onClick={clearSelection}>Clear ({selectedClips.length})</button>
              )}
            </div>
            <div className="review-list-scroll">
              {pendingClips.map((clip, idx) => (
                <div
                  key={clip.id}
                  onClick={() => setReviewActiveClip(clip.id)}
                  className={`review-clip-item${clip.id === activeClip?.id ? " active" : ""}`}
                >
                  <input
                    type="checkbox"
                    checked={selectedClips.includes(clip.id)}
                    onChange={(e) => { e.stopPropagation(); toggleClipSelection(clip.id); }}
                    onClick={(e) => e.stopPropagation()}
                    style={{
                      width: 14, height: 14, flexShrink: 0,
                      accentColor: "var(--primary)",
                    }}
                  />
                  <div className="review-clip-thumb">
                    <Play size={10} color="var(--text-4)" />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="review-clip-title">{clip.title ?? `Clip ${idx + 1}`}</div>
                    {clip.viral_score !== undefined && (
                      <div className="review-clip-score" style={{ color: viralColor(clip.viral_score) }}>
                        <TrendingUp size={10} />
                        {clip.viral_score}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right — main view */}
          {activeClip && (
            <div className="review-main">
              {/* Video player */}
              <div className="review-video-area" onClick={togglePlay} style={{ cursor: "pointer" }}>
                <video
                  ref={videoRef}
                  key={activeClip.id}
                  src={clipsApi.streamUrl(activeClip.id)}
                  style={{ maxHeight: "55vh", maxWidth: "100%", display: "block" }}
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  loop
                />
              </div>

              {/* Action bar */}
              <div className="review-controls">
                <button onClick={() => handleReview("approve")} className="review-btn-approve">
                  <CheckCircle size={14} /> Approve
                </button>
                <button onClick={() => handleReview("reject")} className="review-btn-reject">
                  <XCircle size={14} /> Reject
                </button>
                <button
                  onClick={togglePlay}
                  className="icon-btn"
                  style={{ border: "1px solid var(--border-1)", width: 34, height: 34 }}
                  title="Play/Pause (Space)"
                >
                  {isPlaying ? <Pause size={13} /> : <Play size={13} />}
                </button>
                <div className="review-shortcut-hint">
                  <kbd>A</kbd> approve &nbsp;
                  <kbd>R</kbd> reject &nbsp;
                  <kbd>J/K</kbd> navigate &nbsp;
                  <kbd>Space</kbd> play
                </div>
              </div>

              {/* Clip meta panel */}
              <div className="review-meta-panel">
                {/* Title row */}
                <div style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 10 }}>
                  {editingTitle ? (
                    <div style={{ flex: 1, display: "flex", gap: 8 }}>
                      <input
                        autoFocus
                        value={titleDraft}
                        onChange={(e) => setTitleDraft(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleSaveTitle()}
                        className="settings-input"
                        style={{ flex: 1 }}
                      />
                      <button className="btn-primary" onClick={handleSaveTitle} style={{ height: 36, padding: "0 14px" }}>
                        <Check size={13} />
                      </button>
                    </div>
                  ) : (
                    <>
                      <h2 className="review-meta-title" style={{ flex: 1 }}>
                        {activeClip.title ?? "Untitled Clip"}
                      </h2>
                      <button
                        className="icon-btn"
                        onClick={() => { setTitleDraft(activeClip.title ?? ""); setEditingTitle(true); }}
                        title="Edit title"
                        style={{ flexShrink: 0 }}
                      >
                        <Edit2 size={13} />
                      </button>
                    </>
                  )}
                </div>

                {/* Meta chips */}
                <div className="review-meta-row">
                  <span className="review-meta-chip">
                    {formatDuration(activeClip.start_time)} → {formatDuration(activeClip.end_time)}
                  </span>
                  {activeClip.duration !== undefined && (
                    <span className="review-meta-chip">
                      {formatDuration(activeClip.duration)} long
                    </span>
                  )}
                  {activeClip.viral_score !== undefined && (
                    <span className="review-meta-chip" style={{ color: viralColor(activeClip.viral_score), borderColor: viralColor(activeClip.viral_score) + "40" }}>
                      <TrendingUp size={10} /> Score {activeClip.viral_score}/100
                    </span>
                  )}
                </div>

                {/* Hook text */}
                {activeClip.hook_text && (
                  <div className="review-hook">
                    "{activeClip.hook_text}"
                  </div>
                )}

                {/* QC issues */}
                {activeClip.qc_issues.length > 0 && (
                  <div style={{
                    padding: "10px 14px",
                    background: "var(--warning-dim)",
                    border: "1px solid rgba(245,158,11,0.2)",
                    borderRadius: "var(--r-md)",
                    marginBottom: 14,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                      <AlertTriangle size={12} color="var(--warning)" />
                      <span style={{ fontSize: 11, fontWeight: 600, color: "var(--warning)", fontFamily: "var(--font-mono)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                        QC Issues
                      </span>
                    </div>
                    {activeClip.qc_issues.map((issue, i) => (
                      <p key={i} style={{ fontSize: 12, color: "var(--text-2)", marginBottom: 3 }}>
                        · {issue.description}
                      </p>
                    ))}
                  </div>
                )}

                {/* Hashtags */}
                {activeClip.hashtags.length > 0 && (
                  <div className="review-hashtags">
                    {activeClip.hashtags.map((tag) => (
                      <span key={tag} className="review-hashtag">#{tag}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Bulk action floating bar */}
      <BulkActions selectedIds={selectedClips} onClear={clearSelection} />
    </>
  );
}
