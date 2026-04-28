"use client";
import { useState, useCallback, useRef, useEffect } from "react";
import { Settings, Scan, Eye, Save, ChevronDown, Check, AlertCircle, RefreshCw } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { useVideos, useYoutubeStats } from "@/lib/queries";
import api from "@/lib/api";
import { toast } from "sonner";

type CropMode = "blur_pillarbox" | "smart_offset" | "dual_zone" | "center_crop" | "blur_letterbox";
type FacecamPosition = "top_left" | "top_right" | "bottom_left" | "bottom_right" | "top_center_full" | "none";
type CropAnchor = "left" | "center" | "right";

interface CropConfig {
  id?: string;
  channel_id?: string;
  default_vertical_crop_mode: CropMode;
  default_facecam_position: FacecamPosition;
  default_crop_x_offset: number;
  default_crop_anchor: CropAnchor;
  default_dual_zone_split_ratio: number;
  obs_canvas_width: number;
  obs_canvas_height: number;
  obs_fps: number;
  game_profiles?: GameProfile[];
}

interface GameProfile {
  id: string;
  game_name: string;
  aliases: string[];
  vertical_crop_mode: CropMode;
  facecam_position?: string;
  crop_x_offset: number;
  crop_anchor: CropAnchor;
  is_active: boolean;
}

const CROP_MODE_INFO: Record<CropMode, {
  label: string;
  desc: string;
  recommended?: boolean;
  comingSoon?: boolean;
  illustration: React.ReactNode;
}> = {
  center_crop: {
    label: "Center Crop",
    desc: "Potong bagian tengah 9:16 dari frame 16:9. Gameplay penuh tanpa bar, tanpa blur. Cocok untuk Battlefield, FPS, game aksi.",
    recommended: true,
    illustration: (
      <div style={{ width: "100%", height: 80, display: "flex", alignItems: "center", justifyContent: "center", gap: 3 }}>
        <div style={{ width: 10, height: 72, background: "rgba(99,102,241,0.15)", borderRadius: 3, border: "1px dashed rgba(99,102,241,0.2)" }} />
        <div style={{ width: 44, height: 72, background: "rgba(99,102,241,0.9)", borderRadius: 3, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 9, color: "#fff", fontWeight: 700, flexDirection: "column", gap: 2 }}>
          <span>9:16</span>
          <span style={{ fontSize: 7, opacity: 0.8 }}>CROP</span>
        </div>
        <div style={{ width: 10, height: 72, background: "rgba(99,102,241,0.15)", borderRadius: 3, border: "1px dashed rgba(99,102,241,0.2)" }} />
      </div>
    ),
  },
  blur_letterbox: {
    label: "Blur Letterbox",
    desc: "Video 16:9 full width (1.3x zoom, facecam terpotong), blur hanya mengisi area kosong atas/bawah. Gaya Shorts — tidak ada black bars.",
    recommended: true,
    illustration: (
      <div style={{ width: 48, height: 80, margin: "0 auto", borderRadius: 4, overflow: "hidden", border: "1px solid rgba(99,102,241,0.3)", display: "flex", flexDirection: "column" }}>
        <div style={{ flex: "0 0 34%", background: "rgba(30,20,60,0.85)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 6, color: "rgba(255,255,255,0.4)", fontWeight: 600, filter: "blur(1px)" }}>blur</div>
        <div style={{ flex: "0 0 32%", background: "rgba(99,102,241,0.85)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 7, color: "#fff", fontWeight: 700 }}>16:9</div>
        <div style={{ flex: "0 0 34%", background: "rgba(30,20,60,0.85)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 6, color: "rgba(255,255,255,0.4)", fontWeight: 600, filter: "blur(1px)" }}>blur</div>
      </div>
    ),
  },
  blur_pillarbox: {
    label: "Blur Pillarbox",
    desc: "Video asli ditengahkan dengan sisi kiri-kanan diberi blur. Aman untuk semua game.",
    illustration: (
      <div style={{ width: "100%", height: 80, display: "flex", alignItems: "center", justifyContent: "center", gap: 3 }}>
        <div style={{ width: 24, height: 72, background: "rgba(99,102,241,0.3)", borderRadius: 3, filter: "blur(2px)" }} />
        <div style={{ width: 44, height: 72, background: "rgba(99,102,241,0.8)", borderRadius: 3, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, color: "#fff", fontWeight: 700 }}>
          9:16
        </div>
        <div style={{ width: 24, height: 72, background: "rgba(99,102,241,0.3)", borderRadius: 3, filter: "blur(2px)" }} />
      </div>
    ),
  },
  smart_offset: {
    label: "Smart Offset",
    desc: "Crop dari sisi tertentu (kiri/kanan) agar facecam ikut terbawa. Untuk Battlefield, Arc Raiders.",
    illustration: (
      <div style={{ width: "100%", height: 80, display: "flex", alignItems: "center", justifyContent: "center", gap: 2 }}>
        <div style={{ width: 72, height: 72, background: "rgba(99,102,241,0.8)", borderRadius: 3, position: "relative", overflow: "hidden", display: "flex", alignItems: "flex-start", justifyContent: "flex-start" }}>
          <div style={{ position: "absolute", top: 4, left: 4, width: 16, height: 12, background: "#00D4AA", borderRadius: 2, opacity: 0.9, fontSize: 5, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700 }}>CAM</div>
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, color: "rgba(255,255,255,0.5)", fontWeight: 600 }}>9:16</div>
        </div>
        <div style={{ width: 28, height: 72, background: "rgba(99,102,241,0.15)", borderRadius: 3, border: "1px dashed rgba(99,102,241,0.3)" }} />
      </div>
    ),
  },
  dual_zone: {
    label: "Dual Zone",
    desc: "Split 2 zona: facecam full-width atas + gameplay center bawah. Untuk Valorant.",
    illustration: (
      <div style={{ width: 60, height: 80, margin: "0 auto", borderRadius: 4, overflow: "hidden", border: "1px solid rgba(99,102,241,0.3)" }}>
        <div style={{ height: "38%", background: "rgba(0,212,170,0.5)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 7, fontWeight: 700, color: "#fff" }}>FACECAM</div>
        <div style={{ height: "62%", background: "rgba(99,102,241,0.5)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 7, fontWeight: 700, color: "#fff" }}>GAMEPLAY</div>
      </div>
    ),
  },
};

export default function CropConfigPage() {
  const { data: ytData, isLoading: ytLoading } = useYoutubeStats();
  const channelId: string | null = ytData?.accounts?.[0]?.channel_id ?? null;

  const { data: doneVideos = [] } = useVideos({ status: "done" });
  const { data: reviewVideos = [] } = useVideos({ status: "review" });
  const videos = doneVideos.length > 0 ? doneVideos : reviewVideos;

  const [config, setConfig] = useState<CropConfig>({
    default_vertical_crop_mode: "center_crop",
    default_facecam_position: "top_left",
    default_crop_x_offset: 0,
    default_crop_anchor: "left",
    default_dual_zone_split_ratio: 0.38,
    obs_canvas_width: 2560,
    obs_canvas_height: 1440,
    obs_fps: 60,
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [previewB64, setPreviewB64] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [detectedRegion, setDetectedRegion] = useState<{ position: string; x: number; y: number; width: number; height: number } | null>(null);
  const [skipIntroMinutes, setSkipIntroMinutes] = useState(10);
  const previewDebounceRef = useRef<NodeJS.Timeout | null>(null);

  // Load config when channelId is available
  useEffect(() => {
    if (ytLoading) return;
    if (!channelId) {
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const res = await api.get(`/settings/channel/${channelId}/crop-config`);
        setConfig(res.data);
      } catch (e) {
        // Config doesn't exist yet — defaults are fine
      } finally {
        setLoading(false);
      }
    })();
  }, [channelId, ytLoading]);

  const latestVideoId = videos[0]?.id;

  // Auto-refresh preview on config change
  const schedulePreview = useCallback(() => {
    if (!latestVideoId) return;
    if (previewDebounceRef.current) clearTimeout(previewDebounceRef.current);
    previewDebounceRef.current = setTimeout(async () => {
      setPreviewLoading(true);
      try {
        const res = await api.post(`/settings/channel/${channelId}/preview-crop`, {
          video_id: latestVideoId,
          vertical_crop_mode: config.default_vertical_crop_mode,
          crop_x_offset: config.default_crop_x_offset,
          crop_anchor: config.default_crop_anchor,
          timestamp_seconds: 10,
        });
        setPreviewB64(res.data.preview_base64);
      } catch {
        setPreviewB64(null);
      } finally {
        setPreviewLoading(false);
      }
    }, 600);
  }, [channelId, latestVideoId, config.default_vertical_crop_mode, config.default_crop_x_offset, config.default_crop_anchor]);

  useEffect(() => {
    schedulePreview();
  }, [schedulePreview]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put(`/settings/channel/${channelId}/crop-config`, {
        default_vertical_crop_mode: config.default_vertical_crop_mode,
        default_facecam_position: config.default_facecam_position,
        default_crop_x_offset: config.default_crop_x_offset,
        default_crop_anchor: config.default_crop_anchor,
        default_dual_zone_split_ratio: config.default_dual_zone_split_ratio,
        obs_canvas_width: config.obs_canvas_width,
        obs_canvas_height: config.obs_canvas_height,
        obs_fps: config.obs_fps,
      });
      toast.success("✅ Konfigurasi disimpan. Berlaku untuk video baru.");
    } catch {
      toast.error("Gagal menyimpan konfigurasi");
    } finally {
      setSaving(false);
    }
  };

  const handleDetect = async () => {
    if (!latestVideoId) return toast.error("Tidak ada video tersedia untuk deteksi");
    setDetecting(true);
    try {
      const res = await api.post(`/settings/channel/${channelId}/detect-facecam`, {
        video_id: latestVideoId,
        start_offset_seconds: skipIntroMinutes * 60,
      });
      if (res.data.detected) {
        setDetectedRegion(res.data.region);
        const suggested = res.data.suggested_config;
        setConfig((prev) => ({
          ...prev,
          default_vertical_crop_mode: suggested.vertical_crop_mode,
          default_facecam_position: suggested.facecam_position,
          default_crop_x_offset: suggested.crop_x_offset ?? 0,
          default_crop_anchor: suggested.crop_anchor,
        }));
        toast.success(`✅ ${res.data.message}`);
      } else {
        toast.info("Facecam tidak terdeteksi otomatis — atur manual");
      }
    } catch {
      toast.error("Deteksi gagal");
    } finally {
      setDetecting(false);
    }
  };

  const updateMode = (mode: CropMode) => {
    setConfig((prev) => ({ ...prev, default_vertical_crop_mode: mode }));
  };

  // Show loading while fetching YouTube account info
  if (ytLoading || loading) {
    return (
      <>
        <Header breadcrumb={[{ label: "Settings" }, { label: "Vertical Crop" }]} />
        <div className="page-scroll">
          <div className="page-body" style={{ maxWidth: 820, display: "flex", alignItems: "center", justifyContent: "center", minHeight: 300 }}>
            <div style={{ textAlign: "center", color: "var(--text-4)" }}>
              <RefreshCw size={24} style={{ animation: "spin 1s linear infinite", marginBottom: 12 }} />
              <p style={{ fontSize: 13, margin: 0 }}>Memuat konfigurasi...</p>
            </div>
          </div>
        </div>
      </>
    );
  }

  // Show empty state if user hasn't connected a YouTube account
  if (!channelId) {
    return (
      <>
        <Header breadcrumb={[{ label: "Settings" }, { label: "Vertical Crop" }]} />
        <div className="page-scroll">
          <div className="page-body" style={{ maxWidth: 820 }}>
            <div style={{
              padding: "48px 32px", borderRadius: 16, border: "1px solid var(--border-1)",
              background: "var(--bg-2)", textAlign: "center",
            }}>
              <AlertCircle size={36} color="var(--text-4)" style={{ marginBottom: 16, opacity: 0.5 }} />
              <h2 style={{ fontSize: 18, fontWeight: 700, color: "var(--text-1)", marginBottom: 8 }}>
                Belum Ada Akun YouTube
              </h2>
              <p style={{ fontSize: 13, color: "var(--text-3)", marginBottom: 24 }}>
                Hubungkan akun YouTube kamu dulu di halaman Settings sebelum mengatur konfigurasi crop.
              </p>
              <a
                href="/settings"
                style={{
                  display: "inline-flex", alignItems: "center", gap: 6,
                  padding: "10px 20px", borderRadius: 8, fontSize: 13, fontWeight: 600,
                  background: "var(--primary)", color: "#fff", textDecoration: "none",
                }}
              >
                <Settings size={14} />
                Buka Settings
              </a>
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Header breadcrumb={[{ label: "Settings" }, { label: "Vertical Crop" }]} />

      <div className="page-scroll">
        <div className="page-body" style={{ maxWidth: 820 }}>

          {/* Page header */}
          <div style={{ marginBottom: 28 }}>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: "var(--text-1)", marginBottom: 6, display: "flex", alignItems: "center", gap: 8 }}>
              <Settings size={20} color="var(--primary)" />
              Vertical Crop Settings
            </h1>
            <p style={{ fontSize: 13, color: "var(--text-3)", margin: 0 }}>
              Konfigurasi bagaimana video 16:9 (2560×1440) dikonversi ke 9:16 (1080×1920) untuk Shorts.
            </p>
          </div>

          {/* ── Crop Mode Selector ────────────────────────────────────── */}
          <section style={{ marginBottom: 28 }}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: "var(--text-2)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 3, height: 14, background: "var(--primary)", borderRadius: 2, display: "inline-block" }} />
              Mode Crop
            </h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: 12 }}>
              {(Object.keys(CROP_MODE_INFO) as CropMode[]).map((mode) => {
                const info = CROP_MODE_INFO[mode];
                const active = config.default_vertical_crop_mode === mode;
                return (
                  <button
                    key={mode}
                    onClick={() => updateMode(mode)}
                    style={{
                      padding: `${info.recommended ? 38 : 16}px 14px 16px`,
                      borderRadius: 12,
                      border: active
                        ? "2px solid var(--primary)"
                        : "1px solid var(--border-1)",
                      background: active ? "rgba(99,102,241,0.08)" : "var(--bg-2)",
                      cursor: "pointer",
                      textAlign: "left",
                      transition: "all 0.15s",
                      position: "relative",
                      overflow: "hidden",
                    }}
                  >
                    {info.recommended && (
                      <span style={{
                        position: "absolute", top: 0, left: 0, right: 0,
                        fontSize: 9, fontWeight: 700, color: "var(--secondary)",
                        background: "rgba(0,212,170,0.1)",
                        borderBottom: "1px solid rgba(0,212,170,0.2)",
                        padding: "5px 10px",
                        textTransform: "uppercase", letterSpacing: "0.05em",
                        display: "flex", alignItems: "center", gap: 4,
                      }}>
                        ★ Recommended
                      </span>
                    )}
                    <div style={{ marginBottom: 10 }}>{info.illustration}</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: active ? "var(--primary)" : "var(--text-1)", marginBottom: 5 }}>
                      {info.label}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-3)", lineHeight: 1.5 }}>
                      {info.desc}
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          {/* ── Facecam Auto-Detect ───────────────────────────────────── */}
          <section style={{ marginBottom: 28 }}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: "var(--text-2)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 3, height: 14, background: "var(--secondary)", borderRadius: 2, display: "inline-block" }} />
              Deteksi Otomatis
            </h2>
            <div style={{
              padding: "16px 20px",
              background: "var(--bg-2)", border: "1px solid var(--border-1)", borderRadius: 12,
              display: "flex", alignItems: "flex-start", gap: 16, flexWrap: "wrap",
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-1)", marginBottom: 4 }}>
                  Deteksi Facecam dari Video
                </div>
                <div style={{ fontSize: 12, color: "var(--text-3)", lineHeight: 1.5 }}>
                  Analisis video terbaru untuk mendeteksi posisi dan ukuran facecam secara otomatis.
                  Hasilnya akan mengisi form di bawah.
                </div>
                {detectedRegion && (
                  <div style={{
                    marginTop: 8, fontSize: 11, color: "var(--secondary)",
                    fontFamily: "var(--font-mono)", fontWeight: 600,
                  }}>
                    ✓ Terdeteksi di {detectedRegion.position} ({detectedRegion.width}×{detectedRegion.height}px)
                  </div>
                )}
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12 }}>
                  <label style={{ fontSize: 12, color: "var(--text-3)", whiteSpace: "nowrap" }}>
                    Skip intro:
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={120}
                    value={skipIntroMinutes}
                    onChange={(e) => setSkipIntroMinutes(Math.max(0, parseInt(e.target.value) || 0))}
                    style={{
                      width: 64, padding: "4px 8px", borderRadius: 6,
                      background: "var(--bg-3)", border: "1px solid var(--border-2)",
                      color: "var(--text-1)", fontSize: 13, textAlign: "center",
                    }}
                  />
                  <span style={{ fontSize: 12, color: "var(--text-4)" }}>menit</span>
                </div>
              </div>
              <button
                onClick={handleDetect}
                disabled={detecting || !latestVideoId}
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600,
                  background: detecting ? "var(--bg-3)" : "rgba(0,212,170,0.12)",
                  border: "1px solid rgba(0,212,170,0.3)",
                  color: detecting ? "var(--text-4)" : "var(--secondary)",
                  cursor: detecting || !latestVideoId ? "not-allowed" : "pointer",
                  whiteSpace: "nowrap",
                  flexShrink: 0,
                }}
              >
                {detecting ? <RefreshCw size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Scan size={14} />}
                {detecting ? "Menganalisis..." : "Deteksi Facecam"}
              </button>
            </div>
          </section>

          {/* ── Preview ──────────────────────────────────────────────── */}
          <section style={{ marginBottom: 28 }}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: "var(--text-2)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
              <Eye size={12} color="var(--text-4)" />
              Preview
            </h2>
            <div style={{
              background: "var(--bg-2)", border: "1px solid var(--border-1)", borderRadius: 12,
              padding: 16, display: "flex", alignItems: "center", justifyContent: "center",
              minHeight: 200, position: "relative",
            }}>
              {previewLoading && (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, color: "var(--text-4)" }}>
                  <RefreshCw size={20} style={{ animation: "spin 1s linear infinite" }} />
                  <span style={{ fontSize: 12 }}>Generating preview...</span>
                </div>
              )}
              {!previewLoading && previewB64 && (
                <img
                  src={previewB64}
                  alt="Crop preview"
                  style={{ maxHeight: 360, borderRadius: 8, boxShadow: "0 4px 20px rgba(0,0,0,0.4)" }}
                />
              )}
              {!previewLoading && !previewB64 && (
                <div style={{ textAlign: "center", color: "var(--text-4)" }}>
                  <Eye size={28} style={{ opacity: 0.3, marginBottom: 8 }} />
                  <p style={{ fontSize: 12, margin: 0 }}>
                    {latestVideoId ? "Preview akan muncul saat mode dipilih" : "Upload video dulu untuk melihat preview"}
                  </p>
                </div>
              )}
            </div>
          </section>

          {/* ── Manual Override ───────────────────────────────────────── */}
          <section style={{ marginBottom: 28 }}>
            <button
              onClick={() => setShowAdvanced((v) => !v)}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                fontSize: 13, fontWeight: 600, color: "var(--text-3)",
                background: "none", border: "none", cursor: "pointer",
                marginBottom: showAdvanced ? 12 : 0,
              }}
            >
              <ChevronDown
                size={14}
                style={{ transform: showAdvanced ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}
              />
              Manual Override
            </button>

            {showAdvanced && (
              <div style={{
                background: "var(--bg-2)", border: "1px solid var(--border-1)",
                borderRadius: 12, padding: "16px 20px",
                display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16,
              }}>
                {/* Facecam Position */}
                <div>
                  <label style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: 6 }}>
                    Posisi Facecam
                  </label>
                  <select
                    value={config.default_facecam_position}
                    onChange={(e) => setConfig((p) => ({ ...p, default_facecam_position: e.target.value as FacecamPosition }))}
                    className="settings-input"
                  >
                    {["top_left", "top_right", "bottom_left", "bottom_right", "top_center_full", "none"].map((pos) => (
                      <option key={pos} value={pos}>{pos.replace(/_/g, " ")}</option>
                    ))}
                  </select>
                </div>

                {/* Crop Anchor */}
                <div>
                  <label style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: 6 }}>
                    Crop Anchor
                  </label>
                  <div style={{ display: "flex", gap: 6 }}>
                    {(["left", "center", "right"] as CropAnchor[]).map((a) => (
                      <button
                        key={a}
                        onClick={() => setConfig((p) => ({ ...p, default_crop_anchor: a }))}
                        style={{
                          flex: 1, padding: "6px 0", borderRadius: 6, fontSize: 12, fontWeight: 600,
                          background: config.default_crop_anchor === a ? "var(--primary)" : "var(--bg-3)",
                          color: config.default_crop_anchor === a ? "#fff" : "var(--text-3)",
                          border: `1px solid ${config.default_crop_anchor === a ? "var(--primary)" : "var(--border-1)"}`,
                          cursor: "pointer",
                          textTransform: "capitalize",
                        }}
                      >{a}</button>
                    ))}
                  </div>
                </div>

                {/* X Offset */}
                <div style={{ gridColumn: "span 2" }}>
                  <label style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: 6 }}>
                    X Offset: {config.default_crop_x_offset}px
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={500}
                    step={10}
                    value={config.default_crop_x_offset}
                    onChange={(e) => setConfig((p) => ({ ...p, default_crop_x_offset: parseInt(e.target.value) }))}
                    style={{ width: "100%", accentColor: "var(--primary)" }}
                  />
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--text-4)", marginTop: 2 }}>
                    <span>0px</span><span>250px</span><span>500px</span>
                  </div>
                </div>

                {/* OBS Canvas */}
                <div>
                  <label style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: 6 }}>
                    OBS Canvas
                  </label>
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <input
                      type="number"
                      value={config.obs_canvas_width}
                      onChange={(e) => setConfig((p) => ({ ...p, obs_canvas_width: parseInt(e.target.value) || 2560 }))}
                      className="settings-input"
                      style={{ width: 80, textAlign: "center" }}
                    />
                    <span style={{ color: "var(--text-4)", fontSize: 12 }}>×</span>
                    <input
                      type="number"
                      value={config.obs_canvas_height}
                      onChange={(e) => setConfig((p) => ({ ...p, obs_canvas_height: parseInt(e.target.value) || 1440 }))}
                      className="settings-input"
                      style={{ width: 80, textAlign: "center" }}
                    />
                  </div>
                </div>

                {/* OBS FPS */}
                <div>
                  <label style={{ fontSize: 11, fontWeight: 600, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: 6 }}>
                    OBS FPS
                  </label>
                  <select
                    value={config.obs_fps}
                    onChange={(e) => setConfig((p) => ({ ...p, obs_fps: parseInt(e.target.value) }))}
                    className="settings-input"
                    style={{ width: 100 }}
                  >
                    {[24, 30, 60].map((fps) => (
                      <option key={fps} value={fps}>{fps} fps</option>
                    ))}
                  </select>
                </div>
              </div>
            )}
          </section>

          {/* ── Game Profiles (read-only list) ───────────────────────── */}
          {config.game_profiles && config.game_profiles.length > 0 && (
            <section style={{ marginBottom: 28 }}>
              <h2 style={{ fontSize: 13, fontWeight: 700, color: "var(--text-2)", textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 12 }}>
                Game Profiles
              </h2>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {config.game_profiles.filter((p) => p.game_name !== "_default").map((profile) => (
                  <div
                    key={profile.id}
                    style={{
                      display: "flex", alignItems: "center", gap: 12, padding: "10px 14px",
                      background: "var(--bg-2)", border: "1px solid var(--border-1)", borderRadius: 8,
                    }}
                  >
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-1)", flex: 1 }}>
                      {profile.game_name}
                    </span>
                    <span style={{
                      fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 99,
                      background: "rgba(99,102,241,0.12)", color: "var(--primary)",
                      border: "1px solid rgba(99,102,241,0.25)",
                    }}>
                      {profile.vertical_crop_mode.replace(/_/g, " ")}
                    </span>
                    {profile.aliases.length > 0 && (
                      <span style={{
                        fontSize: 11, color: "var(--text-4)", fontFamily: "var(--font-mono)",
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                        maxWidth: 140, flexShrink: 1, minWidth: 0,
                      }}>
                        {profile.aliases.slice(0, 2).join(", ")}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ── Save Button ───────────────────────────────────────────── */}
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <button
              onClick={handleSave}
              disabled={saving}
              className="btn-primary"
              style={{ display: "flex", alignItems: "center", gap: 6, padding: "10px 24px" }}
            >
              {saving ? <RefreshCw size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Save size={14} />}
              {saving ? "Menyimpan..." : "Simpan Konfigurasi"}
            </button>
            <p style={{ fontSize: 11, color: "var(--text-4)", margin: 0 }}>
              ℹ️ Video yang sudah diproses perlu di-reprocess untuk apply setting ini.
            </p>
          </div>

        </div>
      </div>
    </>
  );
}
