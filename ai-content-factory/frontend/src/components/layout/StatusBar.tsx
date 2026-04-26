"use client";
import { useQuery } from "@tanstack/react-query";
import { videosApi } from "@/lib/api";

export function StatusBar() {
  const { data: videos } = useQuery({
    queryKey: ["videos", { status: "processing" }],
    queryFn: () => videosApi.list({ status: "processing" }).then((r) => r.data),
    refetchInterval: 5_000,
  });

  const processing = videos ?? [];

  if (processing.length === 0) return null;

  return (
    <div style={{
      position: "fixed",
      bottom: 16,
      right: 16,
      zIndex: 50,
      display: "flex",
      flexDirection: "column",
      gap: 8,
      maxWidth: 300,
    }}>
      {processing.map((v) => (
        <div
          key={v.id}
          style={{
            background: "var(--bg-2)",
            border: "1px solid var(--border-2)",
            borderRadius: "var(--r-md)",
            padding: "10px 14px",
            display: "flex",
            alignItems: "center",
            gap: 10,
            boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
            backdropFilter: "blur(20px)",
          }}
        >
          {/* Spinner */}
          <div className="spin" style={{
            width: 14,
            height: 14,
            borderRadius: "50%",
            border: "2px solid rgba(124,111,255,0.25)",
            borderTopColor: "var(--primary)",
            flexShrink: 0,
          }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: 12.5,
              fontWeight: 500,
              color: "var(--text-1)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}>
              {v.title ?? "Processing…"}
            </div>
            <div style={{
              fontSize: 11,
              color: "var(--text-3)",
              fontFamily: "var(--font-mono)",
              marginTop: 1,
            }}>
              {v.checkpoint ?? "Queued"}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
