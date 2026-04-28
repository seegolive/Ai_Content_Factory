"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Youtube, Globe, Lock, EyeOff, Check, Loader2, AlertTriangle, ExternalLink, Hash, Tag, FileText, Type, ChevronDown } from "lucide-react";
import { useClip, useClipPublishStatus, useSavePublishSettings, usePublishClip, useResetPublishStatus } from "@/lib/queries";
import { clipsApi } from "@/lib/api";
import { toast } from "sonner";

type Privacy = "public" | "unlisted" | "private";

const PRIVACY_OPTIONS: { value: Privacy; label: string; desc: string; icon: React.ReactNode }[] = [
  { value: "public", label: "Public", desc: "Anyone can search and watch", icon: <Globe size={14} /> },
  { value: "unlisted", label: "Unlisted", desc: "Only people with the link can watch", icon: <EyeOff size={14} /> },
  { value: "private", label: "Private", desc: "Only you can watch", icon: <Lock size={14} /> },
];

const YOUTUBE_CATEGORIES = [
  { id: "20", label: "Gaming" },
  { id: "24", label: "Entertainment" },
  { id: "28", label: "Science & Technology" },
  { id: "22", label: "People & Blogs" },
  { id: "17", label: "Sports" },
  { id: "19", label: "Travel & Events" },
  { id: "23", label: "Comedy" },
  { id: "25", label: "News & Politics" },
  { id: "27", label: "Education" },
];

export default function PublishPage() {
  const { clipId } = useParams<{ clipId: string }>();
  const router = useRouter();

  const { data: clip, isLoading: loadingClip } = useClip(clipId);

  // Form state — initialised from clip.publish_settings
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [hashtagInput, setHashtagInput] = useState("");
  const [hashtags, setHashtags] = useState<string[]>([]);
  const [privacy, setPrivacy] = useState<Privacy>("unlisted");
  const [category, setCategory] = useState("20");
  const [formReady, setFormReady] = useState(false);

  // Video preview token
  const [streamToken, setStreamToken] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Publish state
  const [publishing, setPublishing] = useState(false);
  const [pollEnabled, setPollEnabled] = useState(false);
  const [savedOk, setSavedOk] = useState(false);

  const { mutateAsync: saveSettings, isPending: saving } = useSavePublishSettings();
  const { mutateAsync: publishClip } = usePublishClip();
  const { mutateAsync: resetPublishStatus, isPending: resetting } = useResetPublishStatus();
  const { data: publishStatus } = useClipPublishStatus(clipId, pollEnabled);

  // Populate form from clip data
  useEffect(() => {
    if (!clip || formReady) return;
    const ps = clip.publish_settings ?? {};
    setTitle(ps.title ?? clip.title ?? "");
    setDescription(ps.description ?? clip.description ?? "");
    setHashtags(ps.hashtags ?? clip.hashtags ?? []);
    setPrivacy((ps.privacy as Privacy) ?? "unlisted");
    setCategory(ps.category ?? "20");
    setFormReady(true);
  }, [clip, formReady]);

  // Fetch stream token for video preview
  useEffect(() => {
    if (!clipId) return;
    clipsApi.getStreamToken(clipId)
      .then((r) => setStreamToken(r.data.token))
      .catch(() => {});
  }, [clipId]);

  // Check if already publishing (page reload)
  useEffect(() => {
    if (!clip) return;
    const yt = clip.platform_status?.youtube;
    if (yt?.status === "uploading") {
      setPublishing(true);
      setPollEnabled(true);
    }
  }, [clip]);

  // React to poll result
  useEffect(() => {
    if (!publishStatus) return;
    const yt = publishStatus.youtube;
    if (!yt) return;
    if (yt.status === "published" || yt.status === "failed" || yt.status === "pending") {
      setPublishing(false);
      setPollEnabled(false);
    }
  }, [publishStatus]);

  // ── Validation ────────────────────────────────────────────────────────────
  const [errors, setErrors] = useState<{ title?: string; description?: string }>({});

  function validateForm(): boolean {
    const next: { title?: string; description?: string } = {};
    if (!title.trim()) next.title = "Title is required.";
    else if (title.trim().length > 100) next.title = "Title must be 100 characters or fewer.";
    if (description.length > 5000) next.description = "Description must be 5000 characters or fewer.";
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  const addHashtag = () => {
    const tag = hashtagInput.trim().replace(/^#/, "");
    if (tag && !hashtags.includes(tag)) {
      setHashtags([...hashtags, tag]);
    }
    setHashtagInput("");
  };
  const removeHashtag = (t: string) => setHashtags(hashtags.filter((h) => h !== t));

  const handleSave = async () => {
    if (!validateForm()) return;
    await saveSettings({ clipId, settings: { title, description, hashtags, privacy, category } });
    setSavedOk(true);
    setTimeout(() => setSavedOk(false), 2000);
  };

  const handlePublish = async () => {
    if (!validateForm()) return;
    // Save settings first
    await saveSettings({ clipId, settings: { title, description, hashtags, privacy, category } });
    setPublishing(true);
    setPollEnabled(true);
    try {
      await publishClip({ clipId, platforms: ["youtube"], privacy });
    } catch (err: unknown) {
      setPublishing(false);
      setPollEnabled(false);
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Failed to start publish";
      toast.error(msg);
    }
  };

  if (loadingClip) {
    return (
      <div className="publish-loading">
        <Loader2 className="publish-loading-icon" size={28} />
        <span>Loading clip…</span>
      </div>
    );
  }

  if (!clip) {
    return (
      <div className="publish-loading">
        <AlertTriangle size={28} />
        <span>Clip not found.</span>
      </div>
    );
  }

  const ytStatus = (publishStatus?.youtube ?? clip.platform_status?.youtube) as { status: string; video_id?: string; error?: string } | undefined;
  const isPublished = ytStatus?.status === "published";
  const isFailed = ytStatus?.status === "failed";
  const isUploading = publishing || ytStatus?.status === "uploading";

  // Prefer vertical (9:16) for publish preview — that's what gets uploaded to Shorts
  const hasVertical = !!clip.clip_path_vertical || !!clip.format_generated?.vertical;
  const streamUrl = streamToken
    ? clipsApi.streamUrl(clipId, streamToken, hasVertical ? "vertical" : undefined)
    : null;
  const thumbUrl = clip.thumbnail_path
    ? `/api/v1${clip.thumbnail_path.startsWith("/") ? clip.thumbnail_path : "/" + clip.thumbnail_path}`
    : undefined;

  return (
    <div className="publish-page">
      {/* Header */}
      <div className="publish-header">
        <button className="publish-back-btn" onClick={() => router.back()}>
          <ArrowLeft size={16} />
          <span>Back</span>
        </button>
        <div className="publish-header-title">
          <Youtube size={18} className="publish-header-yt-icon" />
          <span>Publish to YouTube</span>
        </div>
        <div className="publish-header-spacer" />
      </div>

      <div className="publish-body">
        {/* Left — video preview */}
        <div className="publish-preview-col">
          <div className="publish-video-wrap">
            {streamUrl ? (
              <video
                ref={videoRef}
                src={streamUrl}
                poster={thumbUrl}
                controls
                className="publish-video"
              />
            ) : thumbUrl ? (
              <img src={thumbUrl} alt="thumbnail" className="publish-thumb" />
            ) : (
              <div className="publish-video-placeholder">
                <Youtube size={40} />
              </div>
            )}
          </div>

          {/* Clip meta */}
          <div className="publish-clip-meta">
            <div className="publish-meta-row">
              <span className="publish-meta-label">Score</span>
              <span className="publish-meta-value score">{clip.viral_score ?? "—"}</span>
            </div>
            <div className="publish-meta-row">
              <span className="publish-meta-label">Duration</span>
              <span className="publish-meta-value">{clip.duration ? `${Math.round(clip.duration)}s` : "—"}</span>
            </div>
            <div className="publish-meta-row">
              <span className="publish-meta-label">Format</span>
              <span className="publish-meta-value">{clip.format}</span>
            </div>
            <div className="publish-meta-row">
              <span className="publish-meta-label">Type</span>
              <span className="publish-meta-value">{clip.moment_type ?? "—"}</span>
            </div>
          </div>

          {/* Publish status block */}
          {(isUploading || isPublished || isFailed) && (
            <div className={`publish-status-block ${isPublished ? "published" : isFailed ? "failed" : "uploading"}`}>
              {isUploading && (
                <>
                  <Loader2 size={16} className="spin" />
                  <span>Uploading to YouTube…</span>
                </>
              )}
              {isPublished && (
                <>
                  <Check size={16} />
                  <span>Published!</span>
                  {ytStatus?.video_id && (
                    <a
                      href={`https://youtube.com/watch?v=${ytStatus.video_id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="publish-yt-link"
                    >
                      Open on YouTube <ExternalLink size={12} />
                    </a>
                  )}
                </>
              )}
              {isFailed && (
                <>
                  <AlertTriangle size={16} />
                  <span>{ytStatus?.error ?? "Upload failed"}</span>
                </>
              )}
            </div>
          )}
        </div>

        {/* Right — settings form */}
        <div className="publish-form-col">
          <div className="publish-form-section">
            <label className="publish-field-label">
              <Type size={13} />
              Title
            </label>
            <input
              className={`publish-input${errors.title ? " input-error" : ""}`}
              value={title}
              onChange={(e) => { setTitle(e.target.value); if (errors.title) setErrors((p) => ({ ...p, title: undefined })); }}
              maxLength={100}
              placeholder="Enter YouTube title…"
            />
            <span className="publish-char-count">{title.length}/100</span>
            {errors.title && <span className="publish-field-error">{errors.title}</span>}
          </div>

          <div className="publish-form-section">
            <label className="publish-field-label">
              <FileText size={13} />
              Description
            </label>
            <textarea
              className={`publish-textarea${errors.description ? " input-error" : ""}`}
              value={description}
              onChange={(e) => { setDescription(e.target.value); if (errors.description) setErrors((p) => ({ ...p, description: undefined })); }}
              maxLength={5000}
              rows={5}
              placeholder="Add a description…"
            />
            <span className="publish-char-count">{description.length}/5000</span>
            {errors.description && <span className="publish-field-error">{errors.description}</span>}
          </div>

          <div className="publish-form-section">
            <label className="publish-field-label">
              <Hash size={13} />
              Hashtags
            </label>
            <div className="publish-hashtag-input-row">
              <input
                className="publish-input"
                value={hashtagInput}
                onChange={(e) => setHashtagInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " " || e.key === ",") {
                    e.preventDefault();
                    addHashtag();
                  }
                }}
                placeholder="#gaming or press Enter to add"
              />
              <button className="publish-tag-add-btn" onClick={addHashtag}>Add</button>
            </div>
            {hashtags.length > 0 && (
              <div className="publish-tags-list">
                {hashtags.map((t) => (
                  <button key={t} className="publish-tag" onClick={() => removeHashtag(t)}>
                    <Tag size={10} />#{t} ×
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="publish-form-section">
            <label className="publish-field-label">
              <EyeOff size={13} />
              Privacy
            </label>
            <div className="publish-privacy-options">
              {PRIVACY_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  className={`publish-privacy-option ${privacy === opt.value ? "active" : ""}`}
                  onClick={() => setPrivacy(opt.value)}
                >
                  <span className="publish-privacy-icon">{opt.icon}</span>
                  <span className="publish-privacy-label">{opt.label}</span>
                  <span className="publish-privacy-desc">{opt.desc}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="publish-form-section">
            <label className="publish-field-label">
              <ChevronDown size={13} />
              Category
            </label>
            <select
              className="publish-select"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {YOUTUBE_CATEGORIES.map((c) => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>
          </div>

          {/* Actions */}
          <div className="publish-actions">
            <button
              className={`publish-save-btn ${savedOk ? "saved" : ""}`}
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? <Loader2 size={14} className="spin" /> : savedOk ? <Check size={14} /> : null}
              {savedOk ? "Saved!" : "Save Settings"}
            </button>
            <button
              className="publish-publish-btn"
              onClick={handlePublish}
              disabled={isUploading || isPublished}
            >
              {isUploading ? (
                <><Loader2 size={14} className="spin" /> Uploading…</>
              ) : isPublished ? (
                <><Check size={14} /> Published</>
              ) : (
                <><Youtube size={14} /> Publish to YouTube</>
              )}
            </button>
            {isPublished && (
              <button
                className="publish-reset-btn"
                onClick={async () => {
                  await resetPublishStatus(clipId);
                  setPollEnabled(false);
                  setPublishing(false);
                }}
                disabled={resetting}
              >
                {resetting ? <Loader2 size={14} className="spin" /> : null}
                Publish Again
              </button>
            )}
          </div>

          {isPublished && ytStatus?.video_id && (
            <a
              href={`https://youtube.com/watch?v=${ytStatus.video_id}`}
              target="_blank"
              rel="noreferrer"
              className="publish-open-youtube-btn"
            >
              <Youtube size={14} />
              Open on YouTube
              <ExternalLink size={12} />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
