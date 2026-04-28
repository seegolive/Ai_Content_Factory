"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, Link, Loader2, CheckCircle, CloudUpload, Eye, Clock, Users, Play } from "lucide-react";
import { formatFileSize, formatDuration } from "@/lib/utils";
import { useUploadVideo } from "@/lib/queries";
import { videosApi } from "@/lib/api";
import { toast } from "sonner";
import type { VideoPreviewResponse } from "@/types";
import Image from "next/image";

interface VideoUploaderProps {
  onSuccess?: (videoId: string) => void;
}

const QUALITY_OPTIONS = [
  { value: "1080p", label: "1080p", desc: "Full HD" },
  { value: "1440p", label: "1440p", desc: "2K — Recommended" },
  { value: "2160p", label: "2160p", desc: "4K Ultra HD" },
  { value: "best",  label: "Best",  desc: "Highest available" },
];

function formatViews(n?: number): string {
  if (!n) return "";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M views`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K views`;
  return `${n} views`;
}

export function VideoUploader({ onSuccess }: VideoUploaderProps) {
  const [mode, setMode] = useState<"file" | "url">("file");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [urlLoading, setUrlLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [preview, setPreview] = useState<VideoPreviewResponse | null>(null);
  const [quality, setQuality] = useState("1440p");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { mutateAsync: uploadVideo, isPending } = useUploadVideo();

  // Auto-fetch preview when URL changes (debounced)
  useEffect(() => {
    const url = youtubeUrl.trim();
    if (!url || !url.includes("youtube.com/watch") && !url.includes("youtu.be/")) {
      setPreview(null);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setPreviewLoading(true);
      setPreview(null);
      try {
        const res = await videosApi.preview(url);
        setPreview(res.data);
      } catch {
        // silent — URL might still be incomplete
      } finally {
        setPreviewLoading(false);
      }
    }, 800);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [youtubeUrl]);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;
      try {
        const result = await uploadVideo({ file, onProgress: setUploadProgress });
        toast.success("Video uploaded! Processing started.");
        onSuccess?.(result.video_id);
        setUploadProgress(0);
      } catch (err: any) {
        toast.error(err.response?.data?.detail ?? "Upload failed");
        setUploadProgress(0);
      }
    },
    [uploadVideo, onSuccess]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "video/*": [".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"] },
    maxFiles: 1,
    disabled: isPending,
  });

  const handleUrlSubmit = async () => {
    if (!youtubeUrl.trim()) return;
    setUrlLoading(true);
    try {
      const res = await videosApi.fromUrl(youtubeUrl, undefined, quality);
      toast.success(`Queued at ${quality} · Processing started.`);
      onSuccess?.(res.data.video_id);
      setYoutubeUrl("");
      setPreview(null);
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? "Failed to queue URL");
    } finally {
      setUrlLoading(false);
    }
  };

  return (
    <div className="uploader-card">
      {/* Mode tabs */}
      <div className="uploader-tabs">
        <button
          className={`uploader-tab${mode === "file" ? " active" : ""}`}
          onClick={() => setMode("file")}
        >
          <Upload size={12} />
          Upload File
        </button>
        <button
          className={`uploader-tab${mode === "url" ? " active" : ""}`}
          onClick={() => setMode("url")}
        >
          <Link size={12} />
          YouTube URL
        </button>
      </div>

      {mode === "file" ? (
        <div
          {...getRootProps()}
          className={`uploader-dropzone${isDragActive ? " drag-active" : ""}${isPending ? " uploading" : ""}`}
        >
          <input {...getInputProps()} />
          {isPending ? (
            <div className="uploader-progress-wrap">
              <div className="uploader-progress-icon">
                <Loader2 size={22} color="var(--primary-text)" className="spin" />
              </div>
              <div className="uploader-progress-label">Uploading… {uploadProgress}%</div>
              <div className="uploader-progress-bar-bg">
                <div className="uploader-progress-bar-fill" style={{ width: `${uploadProgress}%` }} />
              </div>
            </div>
          ) : (
            <div className="uploader-idle">
              <div className="uploader-idle-icon">
                <CloudUpload size={24} color="var(--primary-text)" />
              </div>
              <div className="uploader-idle-title">
                {isDragActive ? "Drop the video here" : "Drag & drop video"}
              </div>
              <div className="uploader-idle-hint">
                MP4, MOV, MKV, AVI, WEBM &middot; up to{" "}
                <span style={{ color: "var(--primary-text)" }}>5 GB</span>
              </div>
              <span className="btn-primary" style={{ marginTop: 14, pointerEvents: "none" }}>
                <Upload size={12} /> Browse Files
              </span>
            </div>
          )}
        </div>
      ) : (
        <div className="uploader-url-wrap">
          {/* URL input row */}
          <div className="uploader-url-row">
            <div className="uploader-url-input-wrap">
              <Link size={13} color="var(--text-4)" className="uploader-url-icon" />
              <input
                className="uploader-url-input"
                type="url"
                placeholder="https://youtube.com/watch?v=..."
                value={youtubeUrl}
                onChange={(e) => setYoutubeUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !preview && handleUrlSubmit()}
                disabled={urlLoading}
                autoComplete="off"
              />
              {previewLoading && (
                <Loader2 size={13} color="var(--text-3)" className="spin" style={{ flexShrink: 0 }} />
              )}
            </div>
          </div>

          {/* Preview card */}
          {preview && (
            <div className="url-preview-card">
              {/* Thumbnail */}
              {preview.thumbnail_url && (
                <div className="url-preview-thumb">
                  <Image
                    src={preview.thumbnail_url}
                    alt={preview.title}
                    fill
                    sizes="160px"
                    style={{ objectFit: "cover" }}
                    unoptimized
                  />
                  <div className="url-preview-thumb-overlay">
                    <Play size={20} color="#fff" />
                  </div>
                  {preview.duration_seconds != null && (
                    <span className="url-preview-duration">
                      {formatDuration(preview.duration_seconds)}
                    </span>
                  )}
                </div>
              )}

              {/* Info */}
              <div className="url-preview-info">
                <div className="url-preview-title">{preview.title}</div>
                <div className="url-preview-meta">
                  {preview.uploader && (
                    <span><Users size={10} style={{ display: "inline", marginRight: 3 }} />{preview.uploader}</span>
                  )}
                  {preview.view_count != null && (
                    <span><Eye size={10} style={{ display: "inline", marginRight: 3 }} />{formatViews(preview.view_count)}</span>
                  )}
                </div>

                {/* Quality selector */}
                <div className="url-preview-quality-label">Select quality to download:</div>
                <div className="url-preview-quality-grid">
                  {QUALITY_OPTIONS.map((opt) => {
                    const available = preview.available_qualities.some(q =>
                      q.startsWith(opt.value.replace("p", "")) || opt.value === "best"
                    );
                    return (
                      <button
                        key={opt.value}
                        className={`quality-btn${quality === opt.value ? " active" : ""}${!available && opt.value !== "best" ? " unavailable" : ""}`}
                        onClick={() => setQuality(opt.value)}
                        title={opt.desc}
                      >
                        <span className="quality-btn-value">{opt.label}</span>
                        <span className="quality-btn-desc">{opt.desc}</span>
                        {!available && opt.value !== "best" && (
                          <span className="quality-btn-na">N/A</span>
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Submit */}
                <button
                  className="btn-primary"
                  onClick={handleUrlSubmit}
                  disabled={urlLoading}
                  style={{ marginTop: 10, width: "100%" }}
                >
                  {urlLoading ? (
                    <><Loader2 size={13} className="spin" /> Queuing…</>
                  ) : (
                    <><CheckCircle size={13} /> Process at {quality}</>
                  )}
                </button>
              </div>
            </div>
          )}

          {!preview && !previewLoading && (
            <div className="uploader-url-hint">
              Paste a public YouTube URL — preview will appear automatically.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

