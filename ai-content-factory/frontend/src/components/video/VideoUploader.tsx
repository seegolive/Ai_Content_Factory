"use client";
import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, Link, X, Loader2, CheckCircle } from "lucide-react";
import { cn, formatFileSize } from "@/lib/utils";
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
        const result = await uploadVideo({
          file,
          onProgress: setUploadProgress,
        });
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
    accept: {
      "video/*": [".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"],
    },
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
    <div className="glass-card p-6">
      {/* Mode toggle */}
      <div className="flex gap-2 mb-5">
        {(["file", "url"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={cn(
              "px-4 py-2 text-sm rounded-lg font-medium transition-all",
              mode === m
                ? "bg-primary text-white"
                : "text-foreground-muted hover:text-foreground hover:bg-muted/50"
            )}
          >
            {m === "file" ? "Upload File" : "YouTube URL"}
          </button>
        ))}
      </div>

      {mode === "file" ? (
        <div
          {...getRootProps()}
          className={cn(
            "border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-200",
            isDragActive
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/50 hover:bg-muted/20",
            isPending && "pointer-events-none opacity-60"
          )}
        >
          <input {...getInputProps()} />
          {isPending ? (
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="w-10 h-10 text-primary animate-spin" />
              <p className="text-sm text-foreground-muted">Uploading… {uploadProgress}%</p>
              <div className="w-48 bg-muted rounded-full h-1.5">
                <div
                  className="bg-primary h-1.5 rounded-full transition-all"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          ) : isDragActive ? (
            <div className="flex flex-col items-center gap-3">
              <Upload className="w-10 h-10 text-primary" />
              <p className="text-sm text-primary font-medium">Drop it here!</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <Upload className="w-10 h-10 text-foreground-muted" />
              <div>
                <p className="text-sm font-medium text-foreground">
                  Drag & drop or click to upload
                </p>
                <p className="text-xs text-foreground-muted mt-1">
                  MP4, MOV, AVI, MKV, WebM · Max 10 GB
                </p>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="flex gap-3">
          <input
            type="url"
            value={youtubeUrl}
            onChange={(e) => setYoutubeUrl(e.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
            className="flex-1 bg-muted border border-border rounded-lg px-4 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus:outline-none focus:border-primary transition-colors"
            onKeyDown={(e) => e.key === "Enter" && handleUrlSubmit()}
          />
          <button
            onClick={handleUrlSubmit}
            disabled={urlLoading || !youtubeUrl.trim()}
            className="px-5 py-2.5 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {urlLoading && <Loader2 className="w-4 h-4 animate-spin" />}
            Process
          </button>
        </div>
      )}
    </div>
  );
}
