"use client";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, Link, Loader2, CheckCircle, CloudUpload } from "lucide-react";
import { formatFileSize } from "@/lib/utils";
import { useUploadVideo } from "@/lib/queries";
import { videosApi } from "@/lib/api";
import { toast } from "sonner";

interface VideoUploaderProps {
  onSuccess?: (videoId: string) => void;
}

export function VideoUploader({ onSuccess }: VideoUploaderProps) {
  const [mode, setMode] = useState<"file" | "url">("file");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [urlLoading, setUrlLoading] = useState(false);

  const { mutateAsync: uploadVideo, isPending } = useUploadVideo();

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
      const res = await videosApi.fromUrl(youtubeUrl);
      toast.success("YouTube URL queued for processing.");
      onSuccess?.(res.data.video_id);
      setYoutubeUrl("");
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
                MP4, MOV, MKV, AVI, WEBM &middot; up to {" "}
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
          <div className="uploader-url-row">
            <div className="uploader-url-input-wrap">
              <Link size={13} color="var(--text-4)" className="uploader-url-icon" />
              <input
                className="uploader-url-input"
                type="url"
                placeholder="https://youtube.com/watch?v=..."
                value={youtubeUrl}
                onChange={(e) => setYoutubeUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleUrlSubmit()}
                disabled={urlLoading}
              />
            </div>
            <button
              className="btn-primary"
              onClick={handleUrlSubmit}
              disabled={urlLoading || !youtubeUrl.trim()}
              style={{ flexShrink: 0 }}
            >
              {urlLoading ? <Loader2 size={13} className="spin" /> : <CheckCircle size={13} />}
              {urlLoading ? "Queuing…" : "Queue"}
            </button>
          </div>
          <div className="uploader-url-hint">
            Paste a public YouTube URL to download and process it through the pipeline.
          </div>
        </div>
      )}
    </div>
  );
}

